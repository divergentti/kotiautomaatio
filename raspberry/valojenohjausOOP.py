#!/usr/bin/env python3
"""
Tässä versiossa käytetään objektiorientoitunutta lähtökohtaa. Mikäli järjestelmässä on esimerkiksi useita
liiketunnistimia ja useita eri valoryhmiä, on fiksumpaa käyttää yhtä python3-koodia kuin useampaa rinnakkain.

Valojen varsinainen ohjaus tapahtuu mqtt-viesteillä, joita voivat lähettää esimerkiksi lähestymisanturit,
kännykän sovellus tai jokin muu IoT-laite.

Ulkotiloissa valoja on turha sytyttää, jos valoisuus riittää muutenkin. Tieto valoisuudesta saadaan mqtt-kanaviin
valoantureilla, mutta lisätieto auringon nousu- ja laskuajoista voi olla myös tarpeen.

Tämä scripti laskee auringon nousu- ja laskuajat ja lähettää mqtt-komennon valojen
päälle kytkemiseen tai sammuttamiseen. Komennoissa ei ole implementoitu QoS-asetusta. Ne ovat oletuksena 0.


Lisäksi tämä scripti tarkkailee tuleeko liikesensoreilta tietoa liikkeestä ja laittaa valot päälle mikäli
aurinko on jo laskenut ja ajastimella ylläpidetty aika on ylitetty. Liikesensorin mikropython koodin ESP32:lle
löydät githubistani Divergentti-nimellä.

MUUTTUJAT: parametrit.py-tiedostosta tuodaan tarvittavat muuttujat. Tähän scriptiin keskeisesti
vaikuttavat muuttujat ovat:

1. LIIKE_PAALLAPITO_AIKA määrittää miten pitkään valoja pidetään päällä liikkeen havaitsemisen jälkeen (Int sekunteja).
2. VALOT_POIS tarkoittaa ehdotonta aikaa, jolloin valot laitetaan pois (string TT:MM) (ilta)
3. VALO_ENNAKKO_AIKA tarkoittaa aikaa jolloin valot sytytetään ennen auringonnousua (string TT:MM). (aamu)

Ajat ovat paikallisaikaa (parametrit.py-tiedostossa).
Laskennassa hyödynnetään suntime-scriptiä, minkä voit asentaa komennolla:

pip3 install suntime

6.9.2020 Jari Hiltunen
"""

import paho.mqtt.client as mqtt  # mqtt kirjasto
import time
import datetime
from dateutil import tz
import logging
from suntime import Sun
from parametrit import LATITUDI, LONGITUDI, MQTTSERVERIPORTTI, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, \
    VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, VALOT_POIS_KLO_POHJOINEN_1, VALO_ENNAKKO_AIKA_POHJOINEN_1, \
    LIIKETUNNISTIN_POHJOINEN_1, LIIKE_PAALLAPITO_AIKA_POHJOINEN_1, AUTOKATOS_RELE1_1_AIHE, \
    VALOT_POIS_KLO_AUTOKATOS_1, VALO_ENNAKKO_AIKA_AUTOKATOS_1, LIIKETUNNISTIN_ETELA_1, \
    LIIKE_PAALLAPITO_AIKA_AUTOKATOS_1, VARASTO_POHJOINEN_RELE1_MQTTAIHE_1, VALOT_POIS_KLO_ETELA_1, \
    VALO_ENNAKKO_AIKA_ETELA_1, LIIKE_PAALLAPITO_AIKA_ETELA_1, LIIKETUNNISTIN_AUTOKATOS

logging.basicConfig(level=logging.ERROR)
logging.error('Virheet kirjataan lokiin')


''' Globaalit päivämäärämuuttujat'''
aikavyohyke = tz.tzlocal()

''' Globaalit muuttujat ja liipaisimet '''
aurinko_laskenut = False
aika_nyt = datetime.datetime.now().astimezone(aikavyohyke)
ohjausobjektit = []

''' testaamista varten
testitunnit = 18
testiminuutit = 0
'''


''' Laskentaobjektit - longitudin ja latitudin saat osoitteesi perusteella Google Mapsista '''
aurinko = Sun(LATITUDI, LONGITUDI)
''' Yhteysobjektit '''
mqttvalot = mqtt.Client("valojenohjaus-ohjaus-OOP")
mqttvalot.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari

def yhdista(mqttvalot, userdata, flags, rc):
    """ Tilataan aiheet mqtt-palvelimelle. [0] ohjausobjekteissa tarkoittaa liikeanturia """
    if mqttvalot.isconnected() is False:
        try:
            mqttvalot.connect_async(MQTTSERVERI, MQTTSERVERIPORTTI, 60)  # yhdista mqtt-brokeriin
        except OSError as e:
            raise Exception("MQTT-palvelinongelma! %s" % mqttvalot.is_connected())
    else:
        print("Yhdistetty statuksella: " + str(rc))
        # mqttvalot.subscribe("$SYS/#")
        for z in range(len(ohjausobjektit)):
            mqttvalot.subscribe(ohjausobjektit[z][0].liikeaihe)


def pura_yhteys():
    mqttvalot.loop_stop()
    try:
        mqttvalot.disconnect()
    except OSError as e:
        raise Exception("MQTT-palvelinongelma! %s" % mqttvalot.is_connected())


class Valojenohjaus:
    """ Konstruktorissa muodostetaan valoja ohjaava objekti, jota päivitetään loopissa """
    global mqttvalot, aika_nyt

    def __init__(self, ohjausaihe, aamu_paalle_aika, ilta_pois_aika):  # konstruktori
        """
       1. IN: aihe string
       2. IN: aamu_paalle_aika on aika joka pidetään valoja päällä ennen ennakko_aika loppumista mikäli
          aurinko laskenut (TT:MM) esimerkiksi 08:00 saakka
       3. IN: ilta_pois_aika tarkoittaa ehdotonta aikaa, jolloin valot laitetaan pois (string TT:MM)
          esimerkiksi 21:00

       """

        if (ohjausaihe is None) or (aamu_paalle_aika is None) or (ilta_pois_aika is None):
            raise Exception("Aihe tai aika puuttuu!")
        self.ohjausaihe = ohjausaihe
        """ 2. paalle_aika tarkoittaa aikaa mihin saakka pidetään valoja päällä ellei aurinko ole noussut """
        self.aamu_paalla_tunnit, self.aamu_paalla_minuutit = map(int, aamu_paalle_aika.split(':'))
        """ 3. valot_pois tarkoittaa aikaa jolloin valot tulee viimeistään sammuttaa päivänpituudesta riippumatta """
        self.ilta_pois_tunnit, self.ilta_pois_minuutit = map(int, ilta_pois_aika.split(':'))

        # Objektin luontihekten aika
        self.aamu_paalle_aika = aika_nyt.replace(hour=self.aamu_paalla_tunnit, minute=self.aamu_paalla_minuutit)
        self.ilta_pois_aika = aika_nyt.replace(hour=self.ilta_pois_tunnit, minute=self.ilta_pois_minuutit)

        self.valot_paalla = False
        self.pitoajalla = False
        self.liikeyllapitoajalla = False

        ''' Päivämäärämuuttujien alustus'''
        self.valot_ohjattu_pois = None
        self.valot_ohjattu_paalle = None


    def tilaa_aihe(self):
        mqttvalot.subscribe(self.ohjausaihe)  # tilaa aihe

    def poista_aihe(self):
        mqttvalot.unsubscribe(self.ohjausaihe)  # poista aihe

    def uusi_valo_paalle_aika(self):
        #  Aika ennen auringonnousua
        self.aamu_paalle_aika = aika_nyt.replace(hour=self.aamu_paalla_tunnit, minute=self.aamu_paalla_minuutit)
        return self.aamu_paalle_aika

    def uusi_valo_pois_aika(self):
        #  Aika illalla jolloin valot sammutetaan
        self.ilta_pois_aika = aika_nyt.replace(hour=self.ilta_pois_tunnit, minute=self.ilta_pois_minuutit)
        return self.ilta_pois_aika

    def muuta_valo_pois_aika(self, tunnit, minuutit):
        #  IN: tunnit ja minuutit int
        if (tunnit < 0) or (tunnit > 24) or (minuutit < 0) or (minuutit > 59):
            print("Valojen aikamuutoksessa väärä arvo!")
            return False
        else:
            self.ilta_pois_aika = aika_nyt.replace(hour=tunnit, minute=minuutit)
            return self.ilta_pois_aika

    def valojen_ohjaus(self, status):
        """ IN: status on joko int 1 tai 0 riippuen siitä mitä releelle lähetetään """
        if status == 0:
            self.valot_paalla = False
        else:
            self.valot_paalla = True
        try:
            mqttvalot.publish(self.ohjausaihe, payload=status, retain=True)

        except AttributeError:
            pass

        except OSError as e:
            raise Exception("Virhetila %s", e)


class Liikeohjaus:
    global mqttvalot
    """ Konstruktorissa muodostetaan liikettä havainnoivat objektit """

    def __init__(self, liikeaihe, paallapitoaika):
        """ IN: aihe (str) ja päälläpitoaika sekunteja (int) """
        if (liikeaihe is None) or (paallapitoaika is None):
            raise Exception("Aihe tai päälläpitoaika puuttuu!")
        self.liikeaihe = liikeaihe
        #  Aihe tilataan silloin kun objekti luodaan
        mqttvalot.subscribe(self.liikeaihe)  # tilaa aihe
        self.paallapitoaika = paallapitoaika
        self.liiketta_havaittu = False
        self.liiketta_havaittu_klo = datetime.datetime.now().astimezone(aikavyohyke)
        self.liike_loppunut_klo = datetime.datetime.now().astimezone(aikavyohyke)
        self.loppumisaika_delta = 0

    def tilaa_aihe(self, mqttvalot, userdata, flags, rc):
        mqttvalot.subscribe(self.liikeaihe)  # tilaa aihe

    def poista_aihe(self):
        mqttvalot.unsubscribe(self.liikeaihe)  # poista aihe


def viestiliike(mqttvalot, userdata, message):
    global ohjausobjektit
    """ Selvitetään mille liikeobjektille viesti kuuluu [0] = liike, [1] = ohjaus """
    #  print("Viesti %s : %s" % (message.topic, message.payload))
    for z in range(len(ohjausobjektit)):
        if message.topic == ohjausobjektit[z][0].liikeaihe:
            viesti = int(message.payload)
            if viesti == 1:
                ohjausobjektit[z][0].liiketta_havaittu = True
                ohjausobjektit[z][0].liiketta_havaittu_klo = datetime.datetime.now().astimezone(aikavyohyke)
            else:
                ohjausobjektit[z][0].liiketta_havaittu = False
                ohjausobjektit[z][0].liike_loppunut_klo = datetime.datetime.now().astimezone(aikavyohyke)
                if ohjausobjektit[z][0].liiketta_havaittu_klo is not None:
                    ohjausobjektit[z][0].loppumisaika_delta = \
                        ohjausobjektit[z][0].liike_loppunut_klo - ohjausobjektit[z][0].liiketta_havaittu_klo
                else:
                    ohjausobjektit[z][0].loppumisaika_delta = 0


def valojen_sytytys_sammutus(objekti):
    global aurinko_laskenut, aika_nyt
    """ IN: valojen ohjaukseen liittyvän objektin nimi """
    try:
        objekti
    except NameError:
        raise Exception("Valojen ohjausobjektia ei löydy!")

    ''' Huom! Palauttaa UTC-ajan ilman astitimezonea'''
    auringon_nousu_tanaan = aurinko.get_sunrise_time().astimezone(aikavyohyke)
    auringon_lasku_tanaan = aurinko.get_sunset_time().astimezone(aikavyohyke)
    auringon_nousu_huomenna = aurinko.get_sunrise_time().astimezone(aikavyohyke) + datetime.timedelta(days=1)

    ''' Mikäli käytät asetuksissa utc-aikaa, käytä alla olevaa riviä 
    ja muista vaihtaa datetime-kutusissa tzInfo=None'''
    aika_nyt = datetime.datetime.now().astimezone(aikavyohyke)

    ''' Testaamista varten 
    global testitunnit, testiminuutit
    testiminuutit = testiminuutit + 1
    if testiminuutit >= 60:
        testiminuutit = 0
        testitunnit = testitunnit + 1
        if testitunnit >= 24:
            testitunnit = 0
    aika_nyt = aika_nyt.replace(hour=testitunnit, minute=testiminuutit)
    print("A: %s - AL: %s - AN: %s" % (aika_nyt.time(), auringon_lasku_tanaan.time(), auringon_nousu_tanaan.time()))
    '''


    ''' Auringon nousu tai laskulogiikka '''

    if (aika_nyt >= auringon_lasku_tanaan) and (aika_nyt < auringon_nousu_huomenna):
        aurinko_noussut = False
        aurinko_laskenut = True
    elif aika_nyt < auringon_nousu_tanaan:
        aurinko_noussut = False
        aurinko_laskenut = True
    else:
        aurinko_noussut = True
        aurinko_laskenut = False

    ''' Testataan ollaanko aamuyössä '''
    if (aika_nyt.hour >= 0) and (aika_nyt <= auringon_nousu_tanaan):
        aamuyossa = True
    else:
        aamuyossa = False

    ''' Valojen sytytys ja sammutuslogiikka'''

    ''' Jos aurinko on laskenut, sytytetään valot, jos ei olla yli sammutusajan ja eri vuorokaudella'''
    if (aurinko_laskenut is True) and (objekti.valot_paalla is False) and (aika_nyt < objekti.uusi_valo_pois_aika()) \
            and (aamuyossa is False):
        objekti.valojen_ohjaus(1)
        objekti.pitoajalla = True
        objekti.valot_ohjattu_paalle = datetime.datetime.now().astimezone(aikavyohyke)
        print("Aurinko laskenut. %s: Valot sytytetty klo: %s" % (objekti.ohjausaihe, objekti.valot_ohjattu_paalle))

    ''' Aurinko laskenut ja valot päällä, mutta sammutusaika saavutettu '''
    if (aurinko_laskenut is True) and (objekti.valot_paalla is True) and (aika_nyt >= objekti.uusi_valo_pois_aika()) \
            and (objekti.liikeyllapitoajalla is False):
        objekti.valojen_ohjaus(0)
        objekti.pitoajalla = False
        objekti.valot_ohjattu_pois = datetime.datetime.now().astimezone(aikavyohyke)
        print("Valot sammutettu. Valot olivat %s päällä %s" % (objekti.ohjausaihe, (objekti.valot_ohjattu_pois
                                                                                    - objekti.valot_ohjattu_paalle)))

    ''' Aurinko laskenut ja aamu lähestyy. Tarkistetaan tuleeko valot sytyttää. '''
    if (objekti.valot_paalla is False) and (aurinko_laskenut is True) and (aamuyossa is True) and \
            (aika_nyt >= objekti.uusi_valo_paalle_aika()):
        objekti.valojen_ohjaus(1)
        objekti.pitoajalla = True
        objekti.valot_ohjattu_paalle = datetime.datetime.now().astimezone(aikavyohyke)
        print("Valot sytytetty %s aamulla ennen auringonnousua klo %s" % (objekti.ohjausaihe,
                                                                          objekti.valot_ohjattu_paalle))

    ''' Jos aurinko noussut, sammutetaan valot '''
    if (aurinko_noussut is True) and (objekti.valot_paalla is True):
        objekti.valojen_ohjaus(0)
        objekti.pitoajalla = False
        objekti.valot_ohjattu_pois = datetime.datetime.now().astimezone(aikavyohyke)
        print("Aurinko noussut %s. Valot %s sammutettu." % (aika_nyt, objekti.ohjausaihe))


def liiketunnistus(liikeobjekti, valoobjekti):
    """ IN: liikeobjektin ja valo-objektin nimet"""
    try:
        liikeobjekti
    except NameError:
        raise Exception("Liikeobjektin nimeä ei löydy!")
    else:
        try:
            valoobjekti
        except NameError:
            raise Exception("Valo-objektin nimeä ei löydy!")

    liikeobjekti.loppumisaika_delta = (datetime.datetime.now().astimezone(aikavyohyke)
                                       - liikeobjekti.liike_loppunut_klo).total_seconds()

    ''' Liiketunnistuksen mukaan valojen sytytys ja sammutus ajan ylityttyä '''
    if (aurinko_laskenut is True) and (valoobjekti.valot_paalla is False) and (liikeobjekti.liiketta_havaittu is True):
        valoobjekti.valojen_ohjaus(1)
        valoobjekti.liikeyllapitoajalla = True
        valoobjekti.valot_ohjattu_paalle = datetime.datetime.now().astimezone(aikavyohyke)
        print("%s: valot sytytetty liiketunnistunnistuksen %s vuoksi klo %s"
              % (valoobjekti.ohjausaihe, liikeobjekti.liikeaihe, valoobjekti.valot_ohjattu_paalle))

    if (aurinko_laskenut is True) and (valoobjekti.valot_paalla is True) and (liikeobjekti.liiketta_havaittu is False) \
            and (liikeobjekti.loppumisaika_delta > liikeobjekti.paallapitoaika) and (valoobjekti.pitoajalla is False):
        valoobjekti.valojen_ohjaus(0)
        print("%s: Valot sammutettu liikkeen %s loppumisen vuoksi. Liikedelta: %s \n"
              % (valoobjekti.ohjausaihe, liikeobjekti.liikeaihe, liikeobjekti.loppumisaika_delta))
        valoobjekti.liikeyllapitoajalla = False
        valoobjekti.valot_ohjattu_pois = datetime.datetime.now().astimezone(aikavyohyke)


def ohjausluuppi():
    global ohjausobjektit
    """ Yhteys on kaikille objekteille sama """
    mqttvalot.on_connect = yhdista  # mita tehdaan kun yhdistetaan brokeriin
    mqttvalot.on_disconnect = pura_yhteys
    mqttvalot.on_message = viestiliike  # maarita mita tehdaan kun viesti saapuu


    """ Valojenohjausobjektit """
    # OUT: ohjausaihe, paalle_aika, pois_aika, ennakko_aika
    pohjoinen = Valojenohjaus(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, VALO_ENNAKKO_AIKA_POHJOINEN_1,
                              VALOT_POIS_KLO_POHJOINEN_1)
    autokatos = Valojenohjaus(AUTOKATOS_RELE1_1_AIHE, VALO_ENNAKKO_AIKA_AUTOKATOS_1, VALOT_POIS_KLO_AUTOKATOS_1)
    etelainen = Valojenohjaus(VARASTO_POHJOINEN_RELE1_MQTTAIHE_1, VALO_ENNAKKO_AIKA_ETELA_1, VALOT_POIS_KLO_ETELA_1)

    """ Liiketunnistimet tilaavat automaattisesti aiheensa """
    # OUT: aihe, paallapitoaika
    autokatos_pir = Liikeohjaus(LIIKETUNNISTIN_AUTOKATOS, LIIKE_PAALLAPITO_AIKA_AUTOKATOS_1)
    etelainen_pir = Liikeohjaus(LIIKETUNNISTIN_ETELA_1, LIIKE_PAALLAPITO_AIKA_ETELA_1)
    pohjoinen_pir = Liikeohjaus(LIIKETUNNISTIN_POHJOINEN_1, LIIKE_PAALLAPITO_AIKA_POHJOINEN_1)

    """ Valo-objektit ja liikeobjektit paritettuna, eli mikä liikeobjekti ohjaa mitäkin valo-objektia """
    ohjausobjektit = [[autokatos_pir, autokatos], [etelainen_pir, etelainen], [pohjoinen_pir, pohjoinen]]

    """ Käynnistetään mqtt-pollaus"""
    mqttvalot.connect_async(MQTTSERVERI, MQTTSERVERIPORTTI, 60)  # yhdista mqtt-brokeriin
    mqttvalot.loop_start()


    """ Suoritetaan looppia kunnes toiminta katkaistaan"""

    while True:
        """ Tarkkaillaan tunnistaako jokin objekti liikettä """
        for z in range(len(ohjausobjektit)):
            liiketunnistus(ohjausobjektit[z][0], ohjausobjektit[z][1])
            valojen_sytytys_sammutus(ohjausobjektit[z][1])

        time.sleep(0.1)  # suoritetaan 0.1s valein
        # time.sleep(0.5)  # testiajoitus

if __name__ == "__main__":
    ohjausluuppi()
