''' Alkuperäinen https://gist.github.com/zufardhiyaulhaq/fe322f61b3012114379235341b935539

Tämä versio on tarkoitettu pelkkien mqtt-virhesanomien siirtämiseen Influx-tietokantaan.

MQTT-sanoma voi olla esimerkiksi muotoa virheet/sijainti/laite/virhe

Kaikki datatyypit ovat str

23.9.2020 Jari Hiltunen
'''

import re
from typing import NamedTuple
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient
from parametrit import INFLUXDB_ADDRESS, INFLUXDB_USER, INFLUXDB_PASSWORD, INFLUXDB_DATABASE, MQTTSERVERI, \
    MQTTSALARI, MQTTKAYTTAJA, MQTTSERVERIPORTTI

''' Tässä kiinteänä koti ensimmäisenä tasona. Huomaa alempana luokka SensorData '''
MQTT_TOPIC = 'virheet/+/+/+'
MQTT_REGEX = 'virheet/([^/]+)/([^/]+)/([^/]+)'
MQTT_CLIENT_ID = 'MQTTInfluxDBSiltaVirheille'

influxdb_client = InfluxDBClient(INFLUXDB_ADDRESS, 8086, INFLUXDB_USER, INFLUXDB_PASSWORD, None)


class SensorData(NamedTuple):
    paikka: str
    sijainti: str
    laite: str
    virhe: str


def on_connect(client, userdata, flags, rc):
    """ The callback for when the client receives a CONNACK response from the server."""
    print('Connected with result code ' + str(rc))
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    """The callback for when a PUBLISH message is received from the server."""
    print(msg.topic + ' ' + str(msg.payload))
    sensor_data = _parse_mqtt_message(msg.topic, msg.payload.decode('utf-8'))
    if sensor_data is not None:
        _send_sensor_data_to_influxdb(sensor_data)


def _parse_mqtt_message(topic, payload):
    match = re.match(MQTT_REGEX, topic)
    if match:
        paikka = match.group(1)
        ''' Tähän lisätty direction, esimerkiksi etela'''
        sijainti = match.group(2)
        laite = match.group(3)
        if laite == 'status':
            return None
        return SensorData(paikka, sijainti, laite, str(payload))
    else:
        return None


def _send_sensor_data_to_influxdb(sensor_data):
    json_body = [
        {
            'laite': sensor_data.laite,
            'tags': {
                'sijainti': sensor_data.sijainti,
                'paikka': sensor_data.paikka
            },
            'fields': {
                'virhe': sensor_data.virhe
            }
        }
    ]
    influxdb_client.write_points(json_body)


def _init_influxdb_database():
    databases = influxdb_client.get_list_database()
    if len(list(filter(lambda x: x['name'] == INFLUXDB_DATABASE, databases))) == 0:
        influxdb_client.create_database(INFLUXDB_DATABASE)
    influxdb_client.switch_database(INFLUXDB_DATABASE)


def main():
    _init_influxdb_database()

    mqtt_client = mqtt.Client(MQTT_CLIENT_ID)
    mqtt_client.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect(MQTTSERVERI, MQTTSERVERIPORTTI)
    mqtt_client.loop_forever()


if __name__ == '__main__':
    print('MQTT to InfluxDB bridge')
    main()
