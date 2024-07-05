#!/usr/bin/python3
# Copyright (c) 2019 Naoyuki tai
# MIT license - see LICENSE

import os, re, subprocess
from typing import List

from .pci import detect_blacklist_devices
from .component import Component
from ..lib.util import safe_string, get_triage_logger
from enum import Enum
import urllib.parse

tlog = get_triage_logger()

class NetworkDeviceType(Enum):
  Unknown = 0
  Ethernet = 1
  Wifi = 2
  Bluetooth = 3
  Bonded = 4
  Other = 5
  pass


class RFKill(object):

  def __init__(self):
    self.devices = {}
    self.refresh()
    pass

  def refresh(self):
    self.devices = {}
    rfk_root = '/sys/class/rfkill'
    for rfkill in os.listdir(rfk_root):
      wifi_mac = os.path.join(rfk_root, rfkill, 'device', 'macaddress')
      if not os.path.exists(wifi_mac):
        continue
      with open(wifi_mac, encoding="iso-8859-1") as mac:
        macaddress = mac.read()
        self.devices[macaddress] = {}
        pass
      for prop in ['hard', 'soft', 'state']:
        with open(os.path.join(rfk_root, rfkill, prop), encoding="iso-8859-1") as fd:
          self.devices[macaddress][prop] = fd.read().strip()
          pass
        pass
      pass
    pass

  def is_wifi_blocked(self, macaddress):
    if macaddress not in self.devices:
      return None
    return self.devices[macaddress]['hard'] == '1' or self.devices[macaddress]['soft'] == '1'


class NetworkDevice(object):
  
  def __init__(self, device_name=None, device_type=None):
    self.device_type = NetworkDeviceType.Unknown if device_type is None else device_type
    self.device_name = device_name
    self.device_node = os.path.join('/sys/class/net', device_name)
    self.mac_address = None
    self.connected = None

    if self.device_type in [None, NetworkDeviceType.Unknown]:
      wifipath = os.path.join(self.device_node, 'wireless')
      if os.path.exists(wifipath):
        self.device_type = NetworkDeviceType.Wifi
      else:
        self.device_type = NetworkDeviceType.Ethernet
        pass
      pass

    # from /etc/netplan/<.IF-ssh_host_rsa_key_pub.hashed.json>
    self.config = {}

    try:
      with open(os.path.join(self.device_node, "address"), encoding="iso-8859-1") as address:
        self.mac_address = address.read().strip()
        pass
      pass
    except:
      pass
    pass
  
  def set_config(self, config):
    self.config = config
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
    return self.device_type == NetworkDeviceType.Wifi

  def is_ethernet(self):
    return self.device_type == NetworkDeviceType.Ethernet


  def get_device_type_name(self):
    return [ "Unknown", "Ethernet", "WIFI", "Bluetooth", "Bond", "Other"][self.device_type.value]

  pass


#
def detect_net_devices():
  net_devices = []

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
  if ethernet_detected:
    devs = ",".join( [dev.device_name for dev in net_devices])
    tlog.info(f"Ethernet detected. {devs}")
    pass
  return net_devices


def get_transport_scheme(u):
  transport_scheme = None
  try:
    transport_scheme = urllib.parse.urlsplit(u).scheme
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
            

class Networks(Component):
  
  def __init__(self):
    self.networks = detect_net_devices()
    pass
  
  def get_component_type(self):
    return "Network"

  def decision(self, **kwargs):
    decisions = []
    rfkill = RFKill()

    blacklist = detect_blacklist_devices()

    if len(blacklist.nics) > 0:
      msg = "Remove or disable following cards because known to not work\n"
      for card in blacklist.nics:
        msg = msg + "  " + card + "\n"
        pass
      decisions.append( {"component": "Network", "result": False, "message": msg } )
      pass


    if len(self.networks) > 0:
      for netdev in self.networks:
        connected = " and connected" if netdev.is_network_connected() else " not connected"
        if netdev.is_wifi():
          rfk = " and RFKILLed" if rfkill.is_wifi_blocked(netdev.mac_address) else ""
          msg = "WIFI device '{dev}'{rfk} detected{conn}".format(dev=netdev.device_name, rfk=rfk, conn=connected)
          pass
        else:
          msg = "Network device '{dev}' detected{conn}".format(dev=netdev.device_name, conn=connected)
          pass
        decisions.append({"component": self.get_component_type(),
                          "device": netdev.device_name,
                          "device_type": netdev.get_device_type_name(),
                          "result": netdev.is_network_connected(),
                          "message": msg })
        pass
      pass
    else:
      msg = "Network device is not present -- INSTALL NETWORK DEVICE"
      decisions.append({"component": self.get_component_type(),
                        "result": False,
                        "message": msg })
      pass
    return decisions

  def detect_changes(self) -> List[tuple]:
    updates = []
    for netdev in self.networks:
      old_connected = netdev.connected
      new_connected = netdev.is_network_connected()
      if old_connected == new_connected:
        continue
      updates.append(({"component": "Network",
                       "device": netdev.device_name,
                       "device_type": netdev.get_device_type_name()},
                      {"result": netdev.is_network_connected()}))
      pass
    return updates

  pass

