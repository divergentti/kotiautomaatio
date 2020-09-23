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
        vilkuta_ledi(2)
        print('Verkon kokoonpano:', wificlient_if.ifconfig())
        return True
    else:
        return False


def ei_voida_yhdistaa():
    print("Yhteys ei onnistu. Bootataan 1 s. kuluttua")
    vilkuta_ledi(10)
    sleep(1)
    machine.reset()


def vilkuta_ledi(kertaa):
    ledipinni = machine.Pin(2, machine.Pin.OUT)
    for i in range(kertaa):
        ledipinni.on()
        utime.sleep_ms(100)
        ledipinni.off()
        utime.sleep_ms(100)


def aseta_aika():
    try:
        ntptime.settime()
        print(utime.localtime(utime.time()))
    except OSError as e:
        print("NTP-palvelimelta %s ei saatu aikaa! Virhe %s" % (NTPPALVELIN, e))
        ei_voida_yhdistaa()
    try:
        webrepl.start()  # kaynnistetaan WebREPL
    except OSError as e:
        print("WebREPL ei kaynnisty. Virhe %s" % e)
        ei_voida_yhdistaa()

try:
    yhdista_wifi(SSID1, SALASANA1)
    time.sleep(3)
    if wificlient_if.isconnected() is True:
        print("Jatketaan %s verkon kanssa. Signaalitaso %s" % (SSID1, wificlient_if.status('rssi')))
        aseta_aika()
        machine.freq(80000000)  # hidastetaan
    else:
        yhdista_wifi(SSID2, SALASANA2)
        time.sleep(3)
        if wificlient_if.isconnected() is False:
            ei_voida_yhdistaa()
        print("Jatketaan %s verkon kanssa. Signaalitaso %s" % (SSID2, wificlient_if.status('rssi')))
        machine.freq(80000000)  # hidastetaan
        aseta_aika()
except OSError as e:
    ei_voida_yhdistaa()
