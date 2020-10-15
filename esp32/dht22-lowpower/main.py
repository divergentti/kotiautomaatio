"""
Tämä suurimmaksi osaksi deep sleepissä aikaa viettävä scripti on tarkoitettu ESP32-Wroom-NodeMCU:lle.

Tarkoituksena on käyttää pelkkää piiriä, eli kytkentään esimerkiksi träppilanka juottamalla piiriin
ja otetaan siitä suoraan lähtö AM2302 (DHT22)-sensorille. Minimoimalla virrankulutuksen voidaan piiri ja anturi
sijoittaa esimerkiksi ullakolle ja tällöin esimerkiksi paristo tai akku kestää kuukausia.

Kevyessä unessa piiri kuluttaa 0,8mA, syväunessa jossa käytössä on RTC ajastin ja RTC muisti, jota tässä scripitssä
hyödynnetään, kulutus on 10 uA.

Sensori kuluttaa mitatessaan noin 0,5mA ja anturin minimi lukuväli on 2 sekuntia.

Piiri ohjelmoidaan erillisellä ohjelmointilaitteella, joita saa ostettua nimellä "ESP-WROOM-32
Development Board Test Burning Fixture Tool Downloader". Laitteen hinta on noin 10€ ja ESP-piirien
noin 2€ kappale. Itse suosin U-mallista piiriä, johon tarvitaan erillinen antenni, joita löytyy nimellä
2.4GHz 3dBi WiFi Antenna Aerial RP-SMA Male wireless router+ 17cm PCI U.FL IPX to RP SMA Male Pigtail Cable.

Kytkennässä tulee muistaa kytkeä EN-nasta 3,3 voltin jännitteeseen! Viemällä nasta EN tilaan HIGH
piiri kytketään käyttöön. Tarvitaan siis VCC, GND ja AM2302 sensorilta data sopivaan nastaan, esim. IO4.

Testien perusteella WiFi-yhteyden palauttaminen ja kolmen mittauksen luenta ja niiden keskiarvojen lähtys
mqtt brokerille näkyy noin 10 pingin verran, eli aikaa kuluu noin 10 sekuntia päällä. Yleismittarilla mitattuna
maksimikulutus on tuona aikana noin 27mA ja tippuu sen jälkeen alle 1mA arvoon, eli arvoa ei voi lukea.

Tekniset tiedot ESP32-piiristä https://www.espressif.com/en/support/documents/technical-documents
Tekniset tiedot AM2303-sensorista https://datasheetspdf.com/pdf-file/845488/Aosong/AM2303/1


15.10.2020 Jari Hiltunen"""
import time
import machine
import dht
from machine import Pin
from umqttsimple import MQTTClient

# tuodaan parametrit tiedostosta parametrit.py
try:
    from parametrit import CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA, DHT22_LAMPO, \
        DHT22_KOSTEUS, PINNI_NUMERO, DHT22_LAMPO_KORJAUSKERROIN, DHT22_KOSTEUS_KORJAUSKERROIN, NUKKUMIS_AIKA
except ImportError:
    print("Jokin asetus puuttuu parametrit.py-tiedostosta!")
    raise

# dht-kirjasto tukee muitakin antureita kuin dht22
anturi = dht.DHT22(Pin(PINNI_NUMERO))
# virhelaskurin idea on tuottaa bootti jos jokin menee pieleen liian usein
anturivirhe = 0  # virhelaskuria varten
client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)


def lue_lampo_kosteus():
    """ Luetaan 3 arvoa 2s välein ja lasketaan keskiarvo, joka lähtetään mqtt:llä """
    lampo_lista = []  # keskiarvon laskentaa varten
    rh_lista = []  # keskiarvon laskentaa varten
    lukukertoja = 0
    lampo_keskiarvo = 0
    rh_keskiarvo = 0

    while lukukertoja < 3:
        try:
            anturi.measure()
        except OSError:
            print("%s: Sensoria ei voida lukea!")
            return False
        lampo = anturi.temperature() * DHT22_LAMPO_KORJAUSKERROIN
        print('Lampo: %3.1f C' % lampo)
        if (lampo > -40) and (lampo < 100):
            lampo_lista.append(lampo)
        kosteus = anturi.humidity() * DHT22_KOSTEUS_KORJAUSKERROIN
        print('Kosteus: %3.1f %%' % kosteus)
        if (kosteus > 0) and (kosteus <= 100):
            rh_lista.append(kosteus)
        if len(lampo_lista) == 3:
            lampo_keskiarvo = sum(lampo_lista) / len(lampo_lista)
            rh_keskiarvo = sum(rh_lista) / len(rh_lista)
        time.sleep(2)
        lukukertoja = lukukertoja+1
    return [lampo_keskiarvo, rh_keskiarvo]


def laheta_arvot_mqtt(lampo_in, kosteus_in):
    lampo = '{:.1f}'.format(lampo_in)
    kosteus = '{:.1f}'.format(kosteus_in)
    try:
        client.publish(DHT22_LAMPO, str(lampo))
    except OSError:
        print("%s: Arvoa %s ei voida tallentaa mqtt! ")
        return False
    try:
        client.publish(DHT22_KOSTEUS, str(kosteus))
    except OSError:
        print("%s: Arvoa %s ei voida tallentaa mqtt! ")
        return False
    print('Tallennettu %s %s' % (lampo, kosteus))
    return True


def restart_and_reconnect():
    print('%s: Ongelmia. Boottaillaan.')
    machine.reset()
    # resetoidaan


try:
    client.connect()
except OSError:
    print("% s:  Ei voida yhdistaa mqtt! ")
    restart_and_reconnect()

while True:
    try:
        lampo, kosteus = lue_lampo_kosteus()
        laheta_arvot_mqtt(lampo, kosteus)
    except KeyboardInterrupt:
        raise
    print("Nukkumaan %s millisekunniksi!" % NUKKUMIS_AIKA)
    machine.deepsleep(NUKKUMIS_AIKA)
