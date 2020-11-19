"""
OLED näytööe: sh1160-kirjastoa, jonka voit ladata täältä https://github.com/robert-hh/SH1106
CCS811 sensorille:   https://github.com/Notthemarsian/CCS811/blob/master/CCS811.py

Näytön SPI kytkentä esimerkki:

SSD1306       NodeMCU-32S(ESP32)
      GND ----> GND
      VCC ----> 3v3 (3.3V)
       D0 ----> GPIO 18 SCK (SPI Clock)
       D1 ----> GPIO 23 MOSI (sama kuin SDA)
      RES ----> GPIO 17 Reset
       DC ----> GPIO 16 Data/Command select
       CS ----> GPIO  5 Chip Select

I2C kytkentä esimerkki:
    SCL = 22
    SDA = 21

CCS811 muista kytkeä nWake -> GND!


"""


from machine import I2C, SPI, Pin

import sh1106
import ccs811
import time
import uasyncio as asyncio
import utime


class SPI_naytonohjain():

    def __init__(self, res=17, dc=16, cs=5, sck=18, mosi=23, leveys=16, rivit=6, lpikselit=128, kpikselit=64):
        self.rivit = []
        self.nayttotekstit = []
        self.aika = 5  # oletusnäyttöaika
        """ Muodostetaan näytönohjaukseen tarvittavat objektit """
        # SPI-kytkennan pinnit
        self.res = Pin(res)  # reset
        self.dc = Pin(dc)  # data
        self.cs = Pin(cs)  # chip select
        # SPI-objektin luonti, sck = d0, mosi = SDA
        self.spi = SPI(2, baudrate=115200, sck=Pin(sck), mosi=Pin(mosi))
        # naytto-objektin luonti
        self.nayttoleveys = leveys  # merkkiä
        self.nayttorivit = rivit  # riviä
        self.pikselit_leveys = lpikselit  # pikseliä
        self.pikselit_korkeus = kpikselit
        self.naytto = sh1106.SH1106_SPI(self.pikselit_leveys, self.pikselit_korkeus, self.spi, self.dc,
                                        self.res, self.cs)
        self.naytto.poweron()
        self.naytto.init_display()
        self.kaanteinen = False

    async def pitka_teksti_nayttoon(self, teksti, aika):
        self.aika = aika
        self.nayttotekstit.clear()
        self.rivit.clear()
        """ Teksti (str) ja aika (int) miten pitkään tekstiä näytetään """
        self.nayttotekstit = [teksti[y-self.nayttoleveys:y] for y in range(self.nayttoleveys,
                              len(teksti)+self.nayttoleveys, self.nayttoleveys)]
        for y in range(len(self.nayttotekstit)):
            self.rivit.append(self.nayttotekstit[y])
        if len(self.rivit) > self.nayttorivit:
            sivuja = len(self.nayttotekstit) // self.nayttorivit
        else:
            sivuja = 1
        if sivuja == 1:
            for z in range(0, len(self.rivit)):
                self.naytto.text(self.rivit[z], 0, 1 + z * 10, 1)


    async def teksti_riville(self, teksti, rivi, aika):
        self.aika = aika
        """ Teksti (str), rivit (int) ja aika (int) miten pitkään tekstiä näytetään """
        if len(teksti) > self.nayttoleveys:
            self.naytto.text('Rivi liian pitkä!', 0, 1 + rivi * 10, 1)
        elif len(teksti) <= self.nayttoleveys:
            self.naytto.text(teksti, 0, 1 + rivi * 10, 1)


    async def aktivoi_naytto(self):
        self.naytto.sleep(False)
        self.naytto.show()
        await asyncio.sleep(self.aika)
        self.naytto.sleep(True)
        self.naytto.init_display()

    async def kontrasti(self, kontrasti=255):
        if kontrasti > 1 or kontrasti < 255:
            self.naytto.contrast(kontrasti)

    async def kaanteinen_vari(self, kaanteinen=False):
        self.kaanteinen = kaanteinen
        self.naytto.invert(kaanteinen)

    async def kaanna_180_astetta(self, kaanna=False):
        self.naytto.rotate(kaanna)

    async def piirra_kehys(self):
        if self.kaanteinen is False:
            self.naytto.framebuf.rect(1, 1, self.pikselit_leveys-1, self.pikselit_korkeus-1, 0xffff)
        else:
            self.naytto.framebuf.rect(1, 1, self.pikselit_leveys - 1, self.pikselit_korkeus - 1, 0x0000)

    async def piirra_alleviivaus(self, rivi, leveys):
        rivikorkeus = self.pikselit_korkeus / self.nayttorivit
        alkux = 1
        alkuy = 8 + (int(rivikorkeus * rivi))
        merkkileveys = int(8 * leveys)
        if self.kaanteinen is False:
            self.naytto.framebuf.hline(alkux, alkuy, merkkileveys, 0xffff)
        else:
            self.naytto.framebuf.hline(alkux, alkuy, merkkileveys, 0x0000)

    async def resetoi_naytto(self):
        self.naytto.reset()

class KaasuSensori():

    def __init__(self, i2cvayla=0, scl=22, sda=21, taajuus=400000, osoite=90):
        self.i2c = I2C(i2cvayla, scl=Pin(scl), sda=Pin(sda), freq=taajuus)
        self.laiteosoite = osoite
        self.sensori = ccs811.CCS811(self.i2c)
        self.eCO2 = 0
        self.tVOC = 0

    async def lue_arvot(self):
        if self.sensori.data_ready():
            self.eCO2 = self.sensori.eCO2
            self.tVOC = self.sensori.tVOC


def ratkaise_aika():
    (vuosi, kuukausi, kkpaiva, tunti, minuutti, sekunti, viikonpva, vuosipaiva) = utime.localtime()
    paivat = {0: "Ma", 1: "Ti", 2: "Ke", 3: "To", 4: "Pe", 5: "La", 6: "Su"}
    kuukaudet = {1: "Tam", 2: "Hel", 3: "Maa", 4: "Huh", 5: "Tou", 6: "Kes", 7: "Hei", 8: "Elo",
              9: "Syy", 10: "Lok", 11: "Mar", 12: "Jou"}
    #.format(paivat[viikonpva]), format(kuukaudet[kuukausi]),
    paiva = "%s.%s.%s" % (kkpaiva, kuukausi, vuosi)
    kello = "%s:%s:%s" % ("{:02d}".format(tunti), "{:02d}".format(minuutti), "{:02d}".format(sekunti))
    return paiva, kello

async def neiti_aika():
    while True:
        print("Uptime %s" % utime.time())
        await asyncio.sleep_ms(100)



async def main():
    naytin = SPI_naytonohjain()
    kaasusensori = KaasuSensori()
    # tyojono = asyncio.get_event_loop()
    while True:
        """ asyncio.create_task(naytin.pitka_teksti_nayttoon("Pitka teksti nayttoon", 5))
        asyncio.create_task(naytin.teksti_riville("Riville 3", 3, 10))
        asyncio.create_task(naytin.pitka_teksti_nayttoon("Viela pidempi teksti nayttoon", 5)) """
        asyncio.create_task(neiti_aika())
        #  Luetaan arvoja taustalla
        asyncio.create_task(kaasusensori.lue_arvot())
        # await naytin.pitka_teksti_nayttoon("Ilmanlaatumonitorointi v0.01", 5)
        # await naytin.piirra_kehys()
        await naytin.teksti_riville("PVM: %s" % ratkaise_aika()[0], 0, 5)
        await naytin.teksti_riville("KLO: %s" % ratkaise_aika()[1], 1,  5)
        if kaasusensori.eCO2 > 1:
            await naytin.teksti_riville("eCO2: %s" % kaasusensori.eCO2, 3, 5)
        if kaasusensori.tVOC > 1:
            await naytin.teksti_riville("tVOC: %s" % kaasusensori.tVOC, 4, 5)
        await naytin.aktivoi_naytto()
        # await naytin.piirra_alleviivaus(3, 7)
        await asyncio.sleep_ms(100)

asyncio.run(main())
