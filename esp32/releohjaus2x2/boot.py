import utime
import time
import machine
import network
import ntptime
import esp
import webrepl  # webbihallinta - asenna komennolla import webrepl_setup
from time import sleep
# Parametrit tuodaan parametrit.py-tiedostosta
from parametrit import SSID1, SSID2, SALASANA1, SALASANA2, WEBREPL_SALASANA, NTPPALVELIN

machine.freq(240000000)  # Aluksi maksimipotku prosessoriin
esp.osdebug(None)
webrepl.start(password=WEBREPL_SALASANA)
wificlient_if = network.WLAN(network.STA_IF)
wificlient_if.active(False)
ntptime.host = NTPPALVELIN


def yhdista_wifi(ssid_nimi, salasana):
    global wificlient_if
    print("Kokeillaan %s" % ssid_nimi)
    wificlient_if.active(True)
    wificlient_if.connect(ssid_nimi, salasana)
    time.sleep(2)
    if wificlient_if.isconnected():
        print('Verkon kokoonpano:', wificlient_if.ifconfig())
        print("Signaalitaso %s" % (wificlient_if.status('rssi')))
        aseta_aika()
        return True
    else:
        return False


def ei_voida_yhdistaa():
    print("Yhteys ei onnistu. Bootataan 1 s. kuluttua")
    sleep(1)
    machine.reset()


def aseta_aika():
    try:
        ntptime.settime()
        print(utime.localtime(utime.time()))
    except OSError as e:
        print("NTP-palvelimelta %s ei saatu aikaa! Virhe %s" % (NTPPALVELIN, e))
        ei_voida_yhdistaa()
    try:
        webrepl.start()  # kaynnistetaan WebREPL
        machine.freq(80000000)  # hidastetaan
    except OSError as e:
        print("WebREPL ei kaynnisty. Virhe %s" % e)
        ei_voida_yhdistaa()


try:
    yhdista_wifi(SSID1, SALASANA1)
except False:
    try:
        yhdista_wifi(SSID2, SALASANA2)
    except False:
        print("Yhdistys ei onnistu, bootataan!")
        ei_voida_yhdistaa()
