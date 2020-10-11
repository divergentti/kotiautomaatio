""" ESP32-Wroom-NodeMCU ja vastaaville (micropython)

    9.9.2020: Jari Hiltunen

    PIR HC-SR501-sensorille:
    Luetaan liiketunnistimelta tulevaa statustietoa, joko pinni päällä tai pois.
    Mikäli havaitaan liikettä, havaitaan keskeytys ja tämä tieto välitetään mqtt-brokerille.

    Sensori näkee 110 astetta, 7 metriin, kuluttaa 65mA virtaa ja toimii 4.5V - 20V jännitteellä.

    Keskimmäinen potentiometri säätää herkkyyttä, laitimmainen aikaa (0-300s) miten pitkään datapinnissä pysyy
    tila high päällä liikkeen havaitsemisen jälkeen. Blokkausaika on 2.5s eli sitä tiheämmin ei havaita muutosta.

    Jumpperi: alareunassa single triggeri, eli liikkeestä lähetetään vain yksi high-tila (3,3V). Eli
    jos ihminen liikkuu tilassa, high pysyy ylhäällä potentiometrillä säädetyn ajan verran ja palautuu
    nollaan. Yläreunassa repeat triggeri, eli lähetetään high-tilaa (3,3V) niin pitkään kun joku on tilassa.

    Käytä tämän scriptin kanssa repeat-tilaa ja säädä aika minimiin (laitimmainen potentionmetri äärivasen)!

    Kytkentä: keskimmäinen on datapinni (high/low), jumpperin puolella maa (gnd) ja +5V toisella puolella.
    Ota jännite ESP32:n 5V lähdöstä (VIN, alin vasemmalla päältä katsottuna antaa  4.75V).

    MQTT-brokerissa voi olla esimerkiksi ledinauhoja ohjaavat laitteet tai muut toimet, joita
    liiketunnistuksesta tulee aktivoida. Voit liittää tähän scriptiin myös releiden ohjauksen,
    jos ESP32 ohjaa samalla myös releitä.

    MQTT hyödyntää valmista kirjastoa umqttsimple.py joka on ladattavissa:
    https://github.com/micropython/micropython-lib/tree/master/umqtt.simple

    22.9.2020: Paranneltu WiFi-objektin hallintaa ja mqtt muutettu retain-tyyppiseksi.
    24.9.2020: Lisätty virheiden kirjaus tiedostoon ja lähetys mqtt-kanavaan. Poistettu ledivilkutus.
               Virheiden kirjauksessa erottimena toimii ";" eli puolipilkulla erotetut arvot.
    11.10.2020: Lisätty mqtt-pollaus siten, että jos mqtt-viestejä ei kuulu puoleen tuntiin, laite bootataan.
"""
import time
import utime
import machine  # tuodaan koko kirjasto
from machine import Pin
from umqttsimple import MQTTClient
import gc
import os
# tuodaan parametrit tiedostosta parametrit.py
from parametrit import CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, \
    MQTT_SALASANA, PIR_PINNI, AIHE_LIIKETUNNISTIN, AIHE_VIRHEET
# tuodaan bootis wifi-ap:n objekti
from boot import wificlient_if

gc.enable()  # aktivoidaan automaattinen roskankeruu

client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)

# Liikesensorin pinni
pir = Pin(PIR_PINNI, Pin.IN)

# MQTT-uptimelaskuri
mqtt_viimeksi_nahty = utime.ticks_ms()


def raportoi_virhe(virhe):
    # IN: str virhe = virheen tekstiosa
    try:
        tiedosto = open('virheet.txt', "r")
        # mikali tiedosto on olemassa, jatketaan
    except OSError:  # avaus ei onnistu, luodaan uusi
        tiedosto = open('virheet.txt', 'w')
        # virheviestin rakenne: pvm + aika;uptime;laitenimi;ip;virhe;vapaa muisti
    virheviesti = str(ratkaise_aika()) + ";" + str(utime.ticks_ms()) + ";" \
        + str(CLIENT_ID) + ";" + str(wificlient_if.ifconfig()) + ";" + str(virhe) +\
        ";" + str(gc.mem_free())
    tiedosto.write(virheviesti)
    tiedosto.close()


def ratkaise_aika():
    (vuosi, kuukausi, kkpaiva, tunti, minuutti, sekunti, viikonpva, vuosipaiva) = utime.localtime()
    aika = "%s.%s.%s klo %s:%s:%s" % (kkpaiva, kuukausi, vuosi, "{:02d}".format(tunti),
                                      "{:02d}".format(minuutti), "{:02d}".format(sekunti))
    return aika


def mqtt_palvelin_yhdista():
    aika = ratkaise_aika()
    if wificlient_if.isconnected() is True:
        try:
            client.connect()
            print("Yhdistetty %s palvelimeen %s" % (client.client_id, client.server))
            return True
        except OSError as e:
            print("% s:  Ei voida yhdistaa mqtt-palvelimeen! %s " % (aika, e))
            raportoi_virhe(e)
            restart_and_reconnect()
    elif wificlient_if.isconnected() is False:
        print("%s: Yhteys on poikki! Signaalitaso %s " % (aika, wificlient_if.status('rssi')))
        raportoi_virhe("Yhteys poikki rssi: %s" % wificlient_if.status('rssi'))
        restart_and_reconnect()


def laheta_pir(status):
    aika = ratkaise_aika()
    if wificlient_if.isconnected():
        try:
            client.publish(AIHE_LIIKETUNNISTIN, str(status), qos=1, retain=True)  # 1 = liiketta, 0 = liike loppunut
            gc.collect()  # puhdistetaan roskat
            return True
        except OSError as e:
            print("% s:  Ei voida yhdistaa mqtt-palvelimeen! %s " % (aika, e))

            restart_and_reconnect()
    else:
        print("%s: Yhteys on poikki! Signaalitaso %s. Bootataan. " % (aika, wificlient_if.status('rssi')))
        raportoi_virhe("Yhteys poikki rssi: %s" % wificlient_if.status('rssi'))
        restart_and_reconnect()


def restart_and_reconnect():
    aika = ratkaise_aika()
    wificlient_if.disconnect()
    wificlient_if.active(False)
    print('%s: Ongelmia. Boottaillaan 1s kuluttua.' % aika)
    time.sleep(1)
    machine.reset()
    # resetoidaan


def tarkista_uptime(aihe, viesti):
    global mqtt_viimeksi_nahty
    print("Aihe %s ja viesti %s vastaanotettu, nollataan laskuri." % (aihe, viesti))
    mqtt_viimeksi_nahty = utime.ticks_ms()


def tarkista_virhetiedosto():
    try:
        tiedosto = open('virheet.txt', "r")
        # mikali tiedosto on olemassa, jatketaan, silla virheita on ilmoitettu
    except OSError:  # avaus ei onnistu, eli tiedostoa ei ole, jatketaan koska ei virheita
        return
        #  Luetaan tiedoston rivit ja ilmoitetaan mqtt:lla
    rivit = tiedosto.readline()
    while rivit:
        try:
            client.publish(AIHE_VIRHEET, str(rivit), retain=False)
            rivit = tiedosto.readline()
        except OSError as e:
            #  Ei onnistu, joten bootataan
            restart_and_reconnect()
    #  Tiedosto luettu ja mqtt:lla ilmoitettu, suljetaan ja poistetaan se
    tiedosto.close()
    os.remove('virheet.txt')


def seuraa_liiketta():
    time.sleep(3)
    mqtt_palvelin_yhdista()
    tarkista_virhetiedosto()
    # statuskyselya varten
    client.set_callback(tarkista_uptime)
    # Tilataan brokerin lahettamat sys-viestit ja nollataan aikalaskuri
    client.subscribe("$SYS/broker/bytes/#")
    on_aika = utime.time()
    ilmoitettu_on = False
    ilmoitettu_off = False

    while True:
        try:
            pir_tila = pir.value()
            if (pir_tila == 0) and (ilmoitettu_off is False):
                aika = ratkaise_aika()
                ''' Nollataan ilmoitus'''
                off_aika = utime.time()
                print("%s UTC : ilmoitettu liikkeen lopusta. Liike kesti %s sekuntia. Uptime %s" %
                      (aika, (off_aika - on_aika), (utime.ticks_ms())))
                laheta_pir(0)
                ilmoitettu_off = True
                ilmoitettu_on = False
            elif (pir_tila == 1) and (ilmoitettu_on is False):
                ''' Liikettä havaittu !'''
                aika = ratkaise_aika()
                on_aika = utime.time()
                print("%s UTC: ilmoitetaan liikkeesta!" % aika)
                laheta_pir(1)
                ilmoitettu_on = True
                ilmoitettu_off = False

        except AttributeError:
            pass

        except KeyboardInterrupt:
            raise

        try:
            client.check_msg()
        except KeyboardInterrupt:
            raise

        if (utime.ticks_diff(utime.ticks_ms(), mqtt_viimeksi_nahty)) > (60 * 30 * 1000):
            # MQTT-palvelin ei ole raportoinut yli puoleen tuntiin
            raportoi_virhe("MQTT-palvelinta ei ole nahty: %s msekuntiin." % (utime.ticks_diff(utime.ticks_ms() ,mqtt_viimeksi_nahty)))
            restart_and_reconnect()

        # lasketaan prosessorin kuormaa
        time.sleep(0.1)


if __name__ == "__main__":
    seuraa_liiketta()
