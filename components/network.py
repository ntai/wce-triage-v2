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

def detect_ethernet():
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
      eth_devices.append(m.group(1))
      pass
    pass
  return { "detected": ethernet_detected, "blacklist": blacklisted_cards, "devices": eth_devices}


def is_network_connected():
  connected = False
  netdir = '/sys/class/net'
  for node in os.listfiles(netdir):
    # Skip loopback
    if node == 'lo':
      continue

    devpath = os.path.join(netdir, node)
    
    try:
      carrierpath = os.path.join(devpath, "carrier")
      carrier = open(carrierpath)
      carrier_state = carrier.read()
      carrier.close()
      if int(carrier_state) == 1:
        connected = True
        pass
      pass
    except:
      pass
  return connected

def get_transport_scheme(u):
  transport_scheme = None
  try:
    transport_scheme = urlparse.urlsplit(u).scheme
  except:
    pass
  return transport_scheme


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
  print(detect_ethernet())
  pass
