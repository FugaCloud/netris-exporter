import re
import yaml
import json
import time
import requests
from os import path
from prometheus_client.core import GaugeMetricFamily, REGISTRY, CounterMetricFamily
from prometheus_client import start_http_server, GC_COLLECTOR, PLATFORM_COLLECTOR, PROCESS_COLLECTOR

class NetrisExporter(object):
    def __init__(self,netris_api,user,password):
        self.netris_api = netris_api
        self.auth = {'user': user, 'password': password, 'authSchemeID': 1}
        self.headers = {"Content-Type": "application/json"}

    def lookingglass(self):
        s = requests.Session()
        r = s.post(self.netris_api + "/api/auth", headers=self.headers, json=self.auth)
        if not r.ok:
            raise Exception(f"{r.status_code}: {r.text}")
        lg = s.get(self.netris_api + "/api/lookingglass", headers=self.headers)
        if not lg.ok:
            raise Exception("computer says " + str(lg.status_code))
        # cat lookingglass.json | jq '.data | map(.) | .[] | {name: .name, hardwareHealth: .hardwareHealth}'
        return lg.json()["data"]

    def get_metrics(self, data):
        for chassis in data:
            name = chassis["name"]
            site = chassis["site"]["name"]
            for check in chassis["hardwareHealth"]:
                if check["check_name"] != "check_port":
                    continue
                status = 0
                if check["port_status"] == "ok":
                    status = 1
                # "swp15 port is UP, 0% RX Utilized of 100 Gbps, 0% TX Utilized of 100 Gbps"
                m = re.match('^\S+', check["message"])
                port = m[0]
                self.status.add_metric([site,name,port], status)
                m = re.match(r".*(?P<rx>\S+)% RX.+(?P<tx>\S+)% TX.*", check["message"])
                if m:
                    self.rx.add_metric([site,name,port], m["rx"])
                    self.tx.add_metric([site,name,port], m["tx"])
                    


    def collect(self):
        data = self.lookingglass()
        self.status = GaugeMetricFamily("netris_port_status", "Port status for network devices managed by Netris", labels=["site","chassis","port"])
        self.rx = GaugeMetricFamily("netris_port_rx", "Port RX utilization for network devices managed by Netris", labels=["site","chassis","port"])
        self.tx = GaugeMetricFamily("netris_port_tx", "Port TX utilization for network devices managed by Netris", labels=["site","chassis","port"])
        self.get_metrics(data)
        yield self.status
        yield self.rx
        yield self.tx

if __name__ == "__main__":
    port = 9000
    frequency = 1
    if path.exists('config.yaml'):
        with open('config.yaml', 'r') as config_file:
            try:
                config = yaml.safe_load(config_file)
                port = int(config['port'])
                frequency = config['scrape_frequency']
                netris_api = config['netris_api']
                user = config['user']
                password = config['password']
            except yaml.YAMLError as error:
                print(error)

    start_http_server(port)
    REGISTRY.unregister(GC_COLLECTOR)
    REGISTRY.unregister(PLATFORM_COLLECTOR)
    REGISTRY.unregister(PROCESS_COLLECTOR)
    REGISTRY.register(NetrisExporter(netris_api,user,password))
    while True: 
        # period between collection
        time.sleep(frequency)
