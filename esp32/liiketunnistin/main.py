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
"""
import time
import utime
import machine  # tuodaan koko kirjasto
from machine import Pin
from umqttsimple import MQTTClient
import gc
# tuodaan parametrit tiedostosta parametrit.py
from parametrit import CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, \
    MQTT_SALASANA, PIR_PINNI, AIHE_LIIKETUNNISTIN
# tuodaan bootis wifi-ap:n objekti
from boot import wificlient_if

gc.enable()  # aktivoidaan automaattinen roskankeruu

print("Prosessorin nopeus asetettu: %s" % machine.freq())

client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)

# Liikesensorin pinni
pir = Pin(PIR_PINNI, Pin.IN)


def ratkaise_aika():
    (vuosi, kuukausi, kkpaiva, tunti, minuutti, sekunti, viikonpva, vuosipaiva) = utime.localtime()
    # paivat = {0: "Ma", 1: "Ti", 2: "Ke", 3: "To", 4: "Pe", 5: "La", 6: "Su"}
    # kuukaudet = {1: "Tam", 2: "Hel", 3: "Maa", 4: "Huh", 5: "Tou", 6: "Kes", 7: "Hei", 8: "Elo",
    #          9: "Syy", 10: "Lok", 11: "Mar", 12: "Jou"}
    # .format(paivat[viikonpva]), format(kuukaudet[kuukausi]),
    aika = "%s.%s.%s klo %s:%s:%s" % (kkpaiva, kuukausi, vuosi, "{:02d}".format(tunti),
                                      "{:02d}".format(minuutti), "{:02d}".format(sekunti))
    return aika


def mqtt_palvelin_yhdista():
    aika = ratkaise_aika()
    if wificlient_if.isconnected() is True:
        try:
            client.set_callback(viestin_saapuessa)
            client.connect()
            client.subscribe(AIHE_LIIKETUNNISTIN)
            print("Yhdistetty %s palvelimeen %s" % (client.client_id, client.server))
            return True
        except OSError as e:
            print("% s:  Ei voida yhdistaa mqtt-palvelimeen! %s " % (aika, e))
            restart_and_reconnect()
    elif wificlient_if.isconnected() is False:
        print("%s: Yhteys on poikki! Signaalitaso %s " % (aika, wificlient_if.status('rssi')))
        restart_and_reconnect()


def viestin_saapuessa():
    #  Tämä on turha, mutta voisi käyttää tilanteessa jossa mqtt-viesti saapuu
    vilkuta_ledi(1)
    return


def laheta_pir(status):
    aika = ratkaise_aika()
    if wificlient_if.isconnected():
        try:
            client.publish(AIHE_LIIKETUNNISTIN, str(status), retain=True)  # 1 = liiketta, 0 = liike loppunut
            gc.collect()  # puhdistetaan roskat
            #  print("Muistia vapaana %s" % gc.mem_free())
            return True
        except OSError as e:
            print("% s:  Ei voida yhdistaa mqtt-palvelimeen! %s " % (aika, e))
            restart_and_reconnect()
    else:
        print("%s: Yhteys on poikki! Signaalitaso %s. Bootataan. " % (aika, wificlient_if.status('rssi')))
        restart_and_reconnect()


def vilkuta_ledi(kertaa):
    ledipinni = machine.Pin(2, machine.Pin.OUT)
    for i in range(kertaa):
        ledipinni.on()
        utime.sleep_ms(100)
        ledipinni.off()
        utime.sleep_ms(100)


def restart_and_reconnect():
    aika = ratkaise_aika()
    wificlient_if.disconnect()
    wificlient_if.active(False)
    print('%s: Ongelmia. Boottaillaan 1s kuluttua.' % aika)
    vilkuta_ledi(10)
    time.sleep(1)
    machine.reset()
    # resetoidaan


def seuraa_liiketta():
    mqtt_palvelin_yhdista()
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
                print("%s UTC : ilmoitettu liikkeen lopusta. Liike kesti %s sekuntia." % (aika, (off_aika - on_aika)))
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

        except KeyboardInterrupt:
            raise

        # lasketaan prosessorin kuormaa
        time.sleep(0.01)


if __name__ == "__main__":
    seuraa_liiketta()
