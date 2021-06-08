import json
from influxdb import InfluxDBClient
import requests
import sys
import datetime
import re

PRE_DEFINED_TAGS = ["tag1", "tag2", "tag3"]
USERNAME = #xxx
PASSHASH = #xxx

INFLUX_DB_NAME = #xxx
INFLUX_TABLE_NAME = #xxx
INFLUX_HOST_IP = #xxx
INFLUX_PORT = 8086
ZABBIX_URL = #x.x.x.x

LOCATION_URL_TEMPLATE = "http://" + ZABBIX_URL + ":443/api/table.json?"\
                        "content=devices&columns=objid,name,status,location=raw&"\
                        "filter_tags=@tag({0})&"\
                        "username={1}&passhash={2}"

tags = []
if len(sys.argv) > 1:
    tags.append(sys.argv[1])
else:
    tags= PRE_DEFINED_TAGS

class VsatLocation(object):
    _id: int
    name: str
    status: str
    status_raw: str
    latitude: float
    longitude: float
    
    def __init__(self, vsat_params: dict):
        super().__init__()
        self._id = int(vsat_params["objid"])
        self.name = vsat_params["name"]
        self.status = vsat_params["status"]
        self.status_raw = vsat_params["status_raw"]
        location = re.split(',|,\s',vsat_params["location_raw"])
        try:
            self.latitude = float(location[0].strip())
            self.longitude = float(location[1].strip())
        except:
            self.latitude = #10.15
            self.longitude = #-15.66

def print_vsat_entries(vsats: list):
    template = '{0:10}\t{1:30}\t{2:10}\t{3:10}\t{4:15}\t{5:15}'
    print(template.format('ID', 'Name', 'Status', 'Status(RAW)', 'Latitude', 'Longitude'))
    print('-' * 100)
    for vsat in vsats:
        print(template.format(vsat._id, vsat.name, vsat.status, vsat.status_raw, vsat.latitude, vsat.longitude))


if __name__ == '__main__':

    for tag in tags:
        location_url = LOCATION_URL_TEMPLATE.format(tag, USERNAME, PASSHASH)
        vsat_entries = []
        json_body = []
        client= InfluxDBClient(host=INFLUX_HOST_IP,port=INFLUX_PORT)
        client.switch_database(INFLUX_DB_NAME)
        
        response = requests.get(location_url)
        response_body = response.content.decode()
        response_entity = json.loads(response_body)

        for vsat in response_entity["devices"]:
            vsat_obj = VsatLocation(vsat)
            if not vsat_obj.name.endswith('-MNG'):
                continue
            vsat_entries.append(vsat_obj)

            json_body.append({"measurement":INFLUX_TABLE_NAME+"_"+tag,
                             "tags":{"id":vsat_obj._id},
                             "fields":{
                                "name":vsat_obj.name,
                                "status":vsat_obj.status,
                                "status_raw":vsat_obj.status_raw,
                                "latitude":vsat_obj.latitude,
                                "longitude":vsat_obj.longitude,
                                "tag": tag}})
        client.write_points(json_body)
        print(f"{datetime.datetime.now()} : Added {len(vsat_entries)} elements to DB, tag: " + tag)
#        print_vsat_entries(vsat_entries)