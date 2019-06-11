import urllib.parse
import os, sys
sys.path.append(os.path.split(os.getcwd())[0])
from components.pci import *
from lib.util import *


# Ethernet device blacklist
#
# SIS 191 gigabit controller 1039:0191 does not work.
# 

ethernet_device_blacklist = { PCI_VENDOR_SIS : { "0191" : True } }


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


def detect_net_devices():
  blacklisted_cards = []
  for pci in list_pci():
    if pci['class'] == 'network':
      pci_address = pci['address']
      vendor_id = pci['vendor']
      deevice_id = pci['device']
      try:
        if ethernet_device_blacklist[vendor_id][pcidevice_id]:
          blacklisted_cards.append(get_lspci_device_desc(pci_address))
          pass
        pass
      except KeyError:
        pass
      pass
    pass
  pass

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

  eth_entry_re = re.compile(r"\d+: (\w+):")
  eth_devices = []
  for line in out.splitlines():
    m = eth_entry_re.match(line.strip())
    if m:
      netdev = NetworkDevice(device_name = m.group(1))
      eth_devices.append(netdev)
      pass
    pass
  return { "detected": ethernet_detected, "blacklist": blacklisted_cards, "devices": eth_devices}


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
  print(detect_net_devices())
  pass
