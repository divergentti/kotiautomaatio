""" ESP32-Wroom-NodeMCU ja vastaaville (micropython)

    Tämä scripti ohjaa kahta 2 Relay modulea siten, että kun mqtt-kanavasta tulee käsky laittaa rele päälle,
    laitetaan ESP32:lta PIN.OUT tilaan 1.

    Esimerkiksi AIHE1_RELE1 voisi olla 'koti/ulko/valaistusautokatos' josta luettu mqtt-viesti 1 laittaisi
    RELE1_PINNI1 arvoksi 1.

    Arvot tuodaan parametrit.py-tiedostosta.

    29.9.2020: Jari Hiltunen


    MQTT hyödyntää valmista kirjastoa umqttsimple.py joka on ladattavissa:
    https://github.com/micropython/micropython-lib/tree/master/umqtt.simple

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
    MQTT_SALASANA, AIHE_VIRHEET, RELE1_PINNI1, RELE1_PINNI2, RELE2_PINNI1, RELE2_PINNI2,\
    AIHE_RELE1_1, AIHE_RELE1_2, AIHE_RELE2_1, AIHE_RELE2_2

# tuodaan bootis wifi-ap:n objekti
from boot import wificlient_if

gc.enable()  # aktivoidaan automaattinen roskankeruu

# Luodaan mqtt-clientin objekti
releclient = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)

# Luodaan releobjektitHuom! Releet kytketty NC (Normally Closed) jolloin 0 = on
rele1_1 = Pin(RELE1_PINNI1, Pin.OUT)
rele1_2 = Pin(RELE1_PINNI2, Pin.OUT)
rele2_1 = Pin(RELE2_PINNI1, Pin.OUT)
rele2_2 = Pin(RELE2_PINNI2, Pin.OUT)


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
            releclient.connect()
            releclient.set_callback(rele_tila)
            releclient.subscribe(AIHE_RELE1_1)
            releclient.subscribe(AIHE_RELE1_2)
            releclient.subscribe(AIHE_RELE2_1)
            releclient.subscribe(AIHE_RELE2_2)
            print("Yhdistetty %s palvelimeen %s" % (releclient.client_id, releclient.server))
            return True
        except OSError as e:
            print("% s:  Ei voida yhdistaa mqtt-palvelimeen! %s " % (aika, e))
            raportoi_virhe(e)
            restart_and_reconnect()
    elif wificlient_if.isconnected() is False:
        print("%s: Yhteys on poikki! Signaalitaso %s " % (aika, wificlient_if.status('rssi')))
        raportoi_virhe("Yhteys poikki rssi: %s" % wificlient_if.status('rssi'))
        restart_and_reconnect()


def rele_tila(rele_ohjaus, msg):
    aika = ratkaise_aika()
    print((rele_ohjaus, msg))
    # Tarkistetaan mille aiheelle viesti tuli
    # Rele 1 pinni 1
    if rele_ohjaus == AIHE_RELE1_1 and msg == b'0':
        print('%s: %s off' % (aika, AIHE_RELE1_1))
        rele1_1.value(0)
    if rele_ohjaus == AIHE_RELE1_1 and msg == b'1':
        print('%s: %s on' % (aika, AIHE_RELE1_1))
        rele1_1.value(1)
    # Rele 1 pinni 2
    if rele_ohjaus == AIHE_RELE1_2 and msg == b'0':
        print('%s: %s off' % (aika, AIHE_RELE1_2))
        rele1_2.value(0)
    if rele_ohjaus == AIHE_RELE1_2 and msg == b'1':
        print('%s: %s on' % (aika, AIHE_RELE1_2))
        rele1_2.value(1)
    # Rele 2 pinni 1
    if rele_ohjaus == AIHE_RELE2_1 and msg == b'0':
        print('%s: %s off' % (aika, AIHE_RELE2_1))
        rele2_1.value(0)
    if rele_ohjaus == AIHE_RELE2_1 and msg == b'1':
        print('%s: %s on' % (aika, AIHE_RELE2_1))
        rele2_1.value(1)
    # REle 2 pinni 2
    if rele_ohjaus == AIHE_RELE2_2 and msg == b'0':
        print('%s: %s off' % (aika, AIHE_RELE2_2))
        rele2_2.value(0)
    if rele_ohjaus == AIHE_RELE2_2 and msg == b'1':
        print('%s: %s on' % (aika, AIHE_RELE2_2))
        rele2_2.value(1)


def restart_and_reconnect():
    aika = ratkaise_aika()
    wificlient_if.disconnect()
    wificlient_if.active(False)
    print('%s: Ongelmia. Boottaillaan 1s kuluttua.' % aika)
    time.sleep(1)
    machine.reset()
    # resetoidaan


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
            releclient.publish(AIHE_VIRHEET, str(rivit), retain=False)
            rivit = tiedosto.readline()
        except OSError as e:
            #  Ei onnistu, joten bootataan
            restart_and_reconnect()
    #  Tiedosto luettu ja mqtt:lla ilmoitettu, suljetaan ja poistetaan se
    tiedosto.close()
    os.remove('virheet.txt')


def rele_looppi():
    time.sleep(3)
    mqtt_palvelin_yhdista()
    tarkista_virhetiedosto()

    while True:
        try:
            releclient.check_msg()

        except KeyboardInterrupt:
            raise

        # lasketaan prosessorin kuormaa
        time.sleep(0.1)


if __name__ == "__main__":
    rele_looppi()