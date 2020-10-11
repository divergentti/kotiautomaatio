""" Boottiversio 1.1

Parametrit tuodaan parametrit.py-tidesosta. Vähintään tarvitaan SSID1 ja SALASANA1 joilla kerrotaan
mihin Wifi-AP halutaan yhdistää. Mikäli WebREPL:ä halutaan käyttää, tulee ensimmäisellä kerralla
käynnistää komento import webrepl_setup, joka luo tiedoston webrepl_cfg.py laitteen juureen.
Komennoilla import os, os.rename('vanha_tiedosto', 'uusi_tiedosto') tai os.remove('tiedostonimi')
voit käsitellä laitteen tiedostoja joko WebREPL tai konsoliportin kautta.

3.10.2020 Jari Hiltunen

Muutokset:
11.10.2020: boot.py ajetaan jostain syystä kahteen kertaan ja siksi käynnistys on hassu. Korjattu käynnistystä.

"""


import utime
import machine
import network
import time
import ntptime
import esp
import webrepl
from time import sleep
from parametrit import SSID1, SSID2, SALASANA1, SALASANA2, WEBREPL_SALASANA, NTPPALVELIN, DHCP_NIMI

wificlient_if = network.WLAN(network.STA_IF)
wificlient_if.active(False)


def ei_voida_yhdistaa():
    print("Yhteys ei onnistu. Bootataan 1 s. kuluttua")
    sleep(1)
    machine.reset()


def aseta_aika():
    if NTPPALVELIN is not None:
        ntptime.host = NTPPALVELIN
    try:
        ntptime.settime()
    except OSError as e:
        print("NTP-palvelimelta %s ei saatu aikaa! Virhe %s" % (NTPPALVELIN, e))
        ei_voida_yhdistaa()
    print("Aika: %s " % str(utime.localtime(utime.time())))
    return True


def kaynnista_webrepl():
    if WEBREPL_SALASANA is not None:
        try:
            webrepl.start(password=WEBREPL_SALASANA)
        except OSError:
            pass
    else:
        try:
            webrepl.start()
        except OSError as e:
            print("WebREPL ei kaynnisty. Virhe %s" % e)
            raise Exception("WebREPL ei ole asenettu! Suorita import webrepl_setup")
    return True


if wificlient_if.isconnected() is False:
    wificlient_if.active(True)
    yritetty_ssid1 = False
    yritetty_ssid2 = False
    if SSID1 is None:
        print("Aseta SSID1 nimi ja salasana paramterit.py-tiedostossa!")
        raise Exception("Aseta SSID1 ja salasana paramterit.py-tiedostossa!")
    print("Kokeillaan verkkoa %s" % SSID1)

    if DHCP_NIMI is not None:
        wificlient_if.config(dhcp_hostname=DHCP_NIMI)

    if (yritetty_ssid1 is False) and (wificlient_if.isconnected() is False):
        try:
            wificlient_if.connect(SSID1, SALASANA1)
            yritetty_ssid1 = True
        except OSError:
            ei_voida_yhdistaa()

    time.sleep(3)

    if (SSID2 is not None) and (wificlient_if.isconnected() is False) and (yritetty_ssid1 is True):
        print("Kokeillaan verkkoa %s" % SSID2)
        try:
            wificlient_if.connect(SSID2, SALASANA2)
            yritetty_ssid2 = True
        except OSError:
            ei_voida_yhdistaa()

    time.sleep(3)

    if (yritetty_ssid1 is True) and (yritetty_ssid2 is True) and (wificlient_if.isconnected() is False):
        print("Ei voida yhdistaa! Bootataan")
        ei_voida_yhdistaa()

    if (yritetty_ssid1 is True) and (yritetty_ssid2 is True) and (wificlient_if.ifconfig()[0] == '0.0.0.0'):
        print("Ei saada IP-osoitetta! Bootataan!")
        ei_voida_yhdistaa()

if (wificlient_if.isconnected() is True) and (wificlient_if.ifconfig()[0] != '0.0.0.0'):
    aseta_aika()
    kaynnista_webrepl()
    print('Laitteen IP-osoite:', wificlient_if.ifconfig()[0])
    print("WiFi-verkon signaalitaso %s" % (wificlient_if.status('rssi')))
