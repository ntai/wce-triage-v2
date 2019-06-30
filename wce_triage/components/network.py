#
# 
#
import urllib.parse
import os, sys
sys.path.append(os.path.split(os.getcwd())[0])
from wce_triage.components.pci import *
from wce_triage.lib.util import *
from wce_triage.lib.hwinfo import *


class NetworkDevice(object):
  Ethernet = 1
  Wifi = 2
  Bluetooth = 3
  Other = 4
  
  def __init__(self, device_name=None, device_type=None):
    self.device_type = device_type
    self.device_name = device_name
    self.device_node = os.path.join('/sys/class/net', device_name)
    self.connected = None

    if self.device_type is None:
      wifipath = os.path.join(self.device_node, 'wireless')
      if os.path.exists(wifipath):
        self.device_type = self.Wifi
      else:
        self.device_type = self.Ethernet
        pass
      pass
    pass
  
  def is_network_connected(self):
    self.connected = False
    try:
      carrierpath = os.path.join(self.device_node, "carrier")
      carrier = open(carrierpath)
      carrier_state = carrier.read()
      carrier.close()
      if int(carrier_state) == 1:
        self.connected = True
        pass
      pass
    except:
      pass
    return self.connected

  # Syntax sugar for triage needs
  def is_wifi(self):
    return self.device_type == self.Wifi

  def is_ethernet(self):
    return self.device_type == self.Ethernet
  pass


#
# FIXME: do something with iwconfig and rfkill
#
def detect_net_devices(hw_info):
  net_devices = []

  if hw_info:
    for netdev in hw_info.get_entries('network'):
      devtype = NetworkDevice.Other
      capabilities = netdev.get("capabilities")
      if capabilities.get("ethernet"):
        devtype = NetworkDevice.Ethernet
        if capabilities.get("wireless"):
          devtype = NetworkDevice.Wifi
          pass
        pass
      else:
        continue
      net_devices.append(NetworkDevice(device_name=netdev.get("logicalname"), device_type=devtype))
      pass
    return net_devices

  ethernet_detected = False
  ip = subprocess.Popen(["ip", "addr", "show", "scope", "link"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  (out, err) = ip.communicate()
  try:
    out = safe_string(out)
    mac_addr = re.findall("link/ether\s+(..):(..):(..):(..):(..):(..)", out)[0]
    if len(mac_addr[3]) > 0:
      ethernet_detected = True
      pass
    pass
  except:
    out = ""
    pass

  net_entry_re = re.compile(r"\d+: (\w+):")
  for line in out.splitlines():
    m = net_entry_re.match(line.strip())
    if m:
      netdev = NetworkDevice(device_name = m.group(1))
      net_devices.append(netdev)
      pass
    pass
  return net_devices


def get_transport_scheme(u):
  transport_scheme = None
  try:
    transport_scheme = urlparse.urlsplit(u).scheme
  except:
    pass
  return transport_scheme


#
# This is to get the IP address of connected server.
# 
def get_router_ip_address():
  netstat = subprocess.Popen("netstat -rn", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
  (out, err) = netstat.communicate()
  routes_re = re.compile(r'([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+\w+\s+\d+\s+\d+\s+\d+\s+(\w+)')
  for line in out.split('\n'):
    m = routes_re.match(line)
    if m and m.group(1) == '0.0.0.0':
      return m.group(2)
    pass
  return None
            

#
if __name__ == "__main__":
  for netdev in detect_net_devices(hw_info()):
    print(netdev.device_name)
    pass
  pass
