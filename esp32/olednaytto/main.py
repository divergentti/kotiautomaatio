"""
Käytetään sh1160-kirjastoa, jonka voit ladata täältä https://github.com/robert-hh/SH1106

SPI kytkentä esimerkki:

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

Malliksi toteutuspohjaa asynkronisesta tavasta hoitaa näytön päivitys.

"""


from machine import SPI, Pin
import sh1106
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

    async def pitka_teksti_nayttoon(self, teksti, aika):
        self.aika = aika
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
            await self.aktivoi_naytto()


    async def teksti_riville(self, teksti, rivi, aika):
        self.aika = aika
        """ Teksti (str), rivit (int) ja aika (int) miten pitkään tekstiä näytetään """
        if len(teksti) > self.nayttoleveys:
            self.naytto.text('Rivi liian pitkä!', 0, 1 + rivi * 10, 1)
        elif len(teksti) <= self.nayttoleveys:
            self.naytto.text(teksti, 0, 1 + rivi * 10, 1)
        await self.aktivoi_naytto()


    async def aktivoi_naytto(self):
        self.naytto.sleep(False)
        self.naytto.show()
        await asyncio.sleep(self.aika)
        self.naytto.sleep(True)
        self.naytto.init_display()

        """display.invert(True) = valkea tausta '
        display.rotate(flag[, update=True])
        display.contrast(level)
        """

async def neiti_aika():
    while True:
        print("Uptime %s" % utime.time())
        await asyncio.sleep_ms(100)



async def main():
    naytin = SPI_naytonohjain()
    # tyojono = asyncio.get_event_loop()
    while True:
        """ asyncio.create_task(naytin.pitka_teksti_nayttoon("Pitka teksti nayttoon", 5))
        asyncio.create_task(naytin.teksti_riville("Riville 3", 3, 10))
        asyncio.create_task(naytin.pitka_teksti_nayttoon("Viela pidempi teksti nayttoon", 5)) """
        asyncio.create_task(neiti_aika())
        await naytin.pitka_teksti_nayttoon("Pitka teksti nayttoon", 5)
        await naytin.teksti_riville("Riville 3", 3, 10)
        await naytin.pitka_teksti_nayttoon("Viela pidempi teksti nayttoon", 5)
        await naytin.teksti_riville("Riville 4", 4, 10)
        await asyncio.sleep_ms(100)

asyncio.run(main())
