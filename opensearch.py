from opensearchpy import OpenSearch
from opensearchpy.exceptions import RequestError
import uuid
import sys
from datetime import datetime
# import os
from dotenv import dotenv_values

config = dotenv_values(".env")

OPTIONS = ["--create_index", "--index_data", "--search", "--delete", "--count"]


host = config.get('OPENSEARCH_HOST')
port = config.get('OPENSEARCH_PORT')
auth = (config.get('OPENSEARCH_UNAME'), config.get('OPENSEARCH_PASSWORD'))
default_index = config.get('OPENSEARCH_INDEX')

client = OpenSearch(
    hosts = [{'host': host, 'port': port}],
    http_compress = True, # enables gzip compression for request bodies
    http_auth = auth,
    use_ssl = True,
    verify_certs = False,
    ssl_assert_hostname = False,
    ssl_show_warn = False,
)

def create_index(index_name):
    index_body = {
        'settings': {
            'index': {
            'number_of_shards': 4
            }
        }
    }
    try:
        client.indices.create(index_name, body=index_body)
    except RequestError as err:
        if (err.error == 'resource_already_exists_exception'):
            print(f'Index {index_name} already exists')
        else:
            print(f'Something went wrong while creating index {index_name}. {err}')
    except Exception as err:
        print(f'Something went wrong while creating index {index_name}. {err}')


def index_data(index_name, data):
    id = uuid.uuid4()
    client.index(
        index = index_name,
        body = data,
        id = id,
    )


def search_data(params, index_name = default_index):
    response = client.search(
        body = params,
        index = index_name
    )
    return response


def count(index_name, query = None):
    return client.count(
        index = index_name,
        body = query,
    )


def delete_data(index_name, id):
    client.delete(
        index = index_name,
        id = id
    )


if __name__ == "__main__":

    args = sys.argv

    try:
        option = args[1]
    except:
        print("No option provided")
        exit()

    if option not in OPTIONS:
        print("Invalid option")
        exit()
    
    if option == "--create_index":
        try:
            index_name = args[2]
            create_index(index_name)
        except:
            print('Please provide index name')

    if option == "--index_data":
        document = {
            "cloud.account.name":"Hitachi Systems India Pvt Ltd",
            "cloud.resource.id":"4",
            "cloud.resource.name":"HSI_Checkpont_firewall",
            "cloud.resource.type":"Check Point Next Generation Firewall",
            "event.action":"Accept",
            "event.category":"ALERT",
            "event.created": datetime.fromisoformat("2024-03-04 00:01:31"),
            "event.id":"15860fe9-1735-4d55-82c7-29bd2f59b493",
            "event.ingested":"2024-03-04 00:06:01",
            "event.original":"Mar 4 00:00:23 10.83.152.8 1 2024-03-03T18:29:35Z chkmgmt-hisysmc CheckPoint 52042 - [action:Accept; flags:393216; ifdir:inbound; ifname:eth5; logid:65536; loguid:{0x65e4c1fc,0x4,0x898530a,0x3fffcb4a...",
            "event.outcome":"Success",
            "event.received":"2024-03-04 00:01:02",
            "event.severity":"0",
            "event.start.day_of_month":"3",
            "event.start.day_of_week":"1",
            "event.start.day_of_year":"63",
            "event.start.hour":"23",
            "event.start.month":"3",
            "event.start.week":"10",
            "event.start.year":"2024",
            "geo.city_name":"San Francisco",
            "geo.continent_code":"NA",
            "geo.country_iso_code":"US",
            "geo.country_name":"United States",
            "geo.is_in_european_union": True,
            "geo.is_satellite_provider":True,
            "geo.location.accuracy_radius":20,
            "geo.location.lat":"37.7308",
            "geo.location.lon":"-122.3838",
            "geo.metro_code":807,
            "geo.name_id":"5391959",
            "geo.postal_code":"94124",
            "geo.region_name":"North America",
            "geo.subdivision_1_iso_code":"CA",
            "geo.subdivision_1_name":"California",
            "geo.subdivision_2_iso_code":"",
            "geo.subdivision_2_name":"California",
            "geo.timezone":"America/Los_Angeles",
            "host.ip":"10.83.152.36",
            "host.name":"chkmgmt-hisysmc",
            "label.siem_id":"{0x65e4c1fc,0x4,0x898530a,0x3fffcb4a}",
            "network.direction":"inbound",
            "network.iana_number":"eth5",
            "network.transport":"TCP",
            "rule.id":"1755",
            "rule.name":"Hitachi Malicious IP detection_HSI",
            "server.address":"122.186.40.52",
            "server.port":"465",
            "source.ip":"162.243.147.25",
            "source.port":"54903",
            "threat.indicator.sightings":True,
            "threat.name":"Activity from malicious address",
            "threat.type":"3588",
            "user.locale_code":"en",
            "user.name.value":"UNKNOWN",
            "user.name.registered_country_geoname_id":"6252001",
            "user.name.represented_country_geoname_id":0
        }
        index_data(default_index, document)

    if option == "--count":
        res = count(default_index)
        print(res['count'])

    if option == "--search":
        query = {
            "size": 1,
            "query": {
                "range": {
                    "event.created": {
                        "gte": datetime.fromisoformat("2022-01-01 00:01:00"),
                        "lte": datetime.fromisoformat("2025-01-01 00:06:00"),
                    }
                },
            }
        }
        res = search_data(query)
        print(res)
