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
        return lg.json()["data"]

    def get_metrics(self, data):
        bgp_states = {
            "Idle": 1,
            "Connect": 2,
            "Active": 3,
            "OpenSent": 4,
            "OpenConfirm": 5,
            "Established": 6,
        }
        for chassis in data:
            name = chassis["name"]
            site = chassis["site"]["name"]
            for check in chassis["hardwareHealth"]:
                m = re.match('^\S+', check["message"])
                port = m[0]
                status = 0
                if check["port_status"] == "ok":
                    status = 1
                if check["check_name"] == "check_port":
                    self.status.add_metric([site,name,port], status)
                    m = re.match(r".*(?P<rx>\S+)% RX.+(?P<tx>\S+)% TX.*", check["message"])
                    if m:
                        self.rx.add_metric([site,name,port], m["rx"])
                        self.tx.add_metric([site,name,port], m["tx"])
                if check["check_name"] == "check_bgp":
                    for p in ["IPv4", "IPv6", "EVPN"]:
                        m = re.search(rf"{p}\(State: (?P<state>\S+), Prefix: (?P<prefix>\S+), Uptime: (?P<uptime>\S+)\)", check["message"])
                        if m:
                            self.bgp_state.add_metric([site,name,port,p], bgp_states[m["state"]])
                            self.bgp_prefix.add_metric([site,name,port,p], m["prefix"])
                if check["check_name"] == "check_agent":
                    self.agent.add_metric([site,name,port], status)
                if check["check_name"] == "check_disk":
                    self.disk_status.add_metric([site,name], status)
                    m = re.search(r"(\d+)%", check["message"])
                    self.disk.add_metric([site,name], int(m.group(1)))
                if check["check_name"] == "check_load":
                    self.load_status.add_metric([site,name], status)
                    m = re.findall(r"(\b\d+\.\d+)", check["message"])
                    self.load.add_metric([site,name,"1m"], float(m[0]))
                    self.load.add_metric([site,name,"5m"], float(m[1]))
                    self.load.add_metric([site,name,"15m"], float(m[2]))
                if check["check_name"] == "check_memory":
                    self.memory_status.add_metric([site,name,port], status)
                    m = re.search(r"(\d+)%", check["message"])
                    self.memory.add_metric([site,name], int(m.group(1)))
                if check["check_name"] == "check_psu":
                    self.psu.add_metric([site,name], status)
                if check["check_name"] == "check_ratio":
                    self.ratio.add_metric([site,name], status)
                if check["check_name"] == "check_temp":
                    self.temp.add_metric([site,name], status)
                if check["check_name"] == "sys_service":
                    self.sys_service.add_metric([site,name], status)
                if check["check_name"] == "xc_service":
                    self.xc_service.add_metric([site,name], status)
                if check["check_name"] == "xc_timesync":
                    self.timesync.add_metric([site,name], status)

    def collect(self):
        data = self.lookingglass()
        self.status = GaugeMetricFamily("netris_port_status", "Port status for network devices managed by Netris", labels=["site","chassis","port"])
        self.rx = GaugeMetricFamily("netris_port_rx", "Port RX utilization for network devices managed by Netris", labels=["site","chassis","port"])
        self.tx = GaugeMetricFamily("netris_port_tx", "Port TX utilization for network devices managed by Netris", labels=["site","chassis","port"])
        self.bgp_state = GaugeMetricFamily("netris_port_bgp_state", "BGP status for network devices managed by Netris", labels=["site","chassis","port","proto"])
        self.bgp_prefix = GaugeMetricFamily("netris_port_bgp_prefix", "BGP prefixes for network devices managed by Netris", labels=["site","chassis","port","proto"])
        self.agent = GaugeMetricFamily("netris_agent", "Netris agent status for network devices managed by Netris", labels=["site","chassis"])
        self.disk = GaugeMetricFamily("netris_disk", "Disk usage for network devices managed by Netris", labels=["site","chassis"])
        self.disk_status = GaugeMetricFamily("netris_disk_status", "Disk status for network devices managed by Netris", labels=["site","chassis"])
        self.load = GaugeMetricFamily("netris_load", "Load on network devices managed by Netris", labels=["site","chassis","avg"])
        self.load_status = GaugeMetricFamily("netris_load_status", "Load on network devices managed by Netris", labels=["site","chassis"])
        self.memory = GaugeMetricFamily("netris_memory", "Memory usage for network devices managed by Netris", labels=["site","chassis"])
        self.memory_status = GaugeMetricFamily("netris_memory_status", "Memory status for network devices managed by Netris", labels=["site","chassis"])
        self.psu = GaugeMetricFamily("netris_psu", "PSU status for network devices managed by Netris", labels=["site","chassis","psu"])
        self.psu_status = GaugeMetricFamily("netris_psu_status", "PSU status for network devices managed by Netris", labels=["site","chassis"])
        self.ratio = GaugeMetricFamily("netris_ratio", "Netris ratio for network devices managed by Netris", labels=["site","chassis","daemon"])
        self.ratio = GaugeMetricFamily("netris_ratio_status", "Netris ratio for network devices managed by Netris", labels=["site","chassis"])
        self.temp = GaugeMetricFamily("netris_temp", "Temperatures for network devices managed by Netris", labels=["site","chassis"])
        self.sys_service = GaugeMetricFamily("netris_sys_service", "Sys service status for network devices managed by Netris", labels=["site","chassis"])
        self.xc_service = GaugeMetricFamily("netris_xc_service", "XC service status for network devices managed by Netris", labels=["site","chassis"])
        self.timesync = GaugeMetricFamily("netris_timesync", "Timesync status for network devices managed by Netris", labels=["site","chassis"])
        self.get_metrics(data)
        yield self.status
        yield self.rx
        yield self.tx
        yield self.bgp_state
        yield self.bgp_prefix
        yield self.agent
        yield self.disk
        yield self.disk_status
        yield self.load
        yield self.load_status
        yield self.memory
        yield self.memory_status
        yield self.psu
        yield self.ratio
        yield self.temp
        yield self.sys_service
        yield self.xc_service
        yield self.timesync

if __name__ == "__main__":
    port = 3000
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
    REGISTRY.register(NetrisExporter(netris_api,user,password))
    while True: 
        # period between collection
        time.sleep(frequency)
