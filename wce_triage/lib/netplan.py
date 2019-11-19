""" netplan.py generates netplan file for triage.

There are two cases, one for during triage where a machine generates a default netplan yaml file,
and other is for server.

"""
from ..const import const
from ..components.network import NetworkDeviceType, NetworkDevice
import sys, os, json, hashlib

indentspace = '  '

class Printer:
  def __init__(self, output):
    self.output = output
    pass

  def print_tree(self, tree, ilevel):
    for elem in tree:
      if isinstance(elem, list):
        self.print_tree( elem, ilevel + 1)
      elif isinstance(elem, dict):
        for key, value in elem.items():
          if isinstance(value, list):
            print( "{indent}{key}:".format(indent=indentspace*ilevel, key=key), file=self.output )
            self.print_tree(value, ilevel+1)
          else:
            print( "{indent}{key}: {value}".format(indent=indentspace*ilevel, key=key, value=value), file=self.output)
            pass
          pass
        pass
      else:
        print(elem, file=self.output)
        pass
      pass
    pass
  pass
      

# Create/generate netplan.yaml file 
def generate_default_netplan_config(filename, devices):
  """create netplan config - used for creating default one."""
  generate_default_config(devices)
  generate_netplan_file(filename, devices)
  pass

#
def format_addresses(addrs):
  return "[ " + ",".join([ "{0}/{1} ".format(addr[0], addr[1]) for addr in addrs ]) + "]"
    

# generate netplan.yaml file from the devices
def generate_netplan_file(filename, devices):
  """generate a netplan file from the devices' config."""
  ifdecl = [ {'version': '2' },
             {'renderer': 'networkd' } ]

  ethernets = []
  wifis = []
  bonds = {}
  
  for dev in devices:
    if dev.config is None:
      continue

    if dev.config["device_type"] == "ethernet":
      dev_config = [ { 'dhcp4': dev.config["dhcp4"] },
                     { 'optional': dev.config["optional"] } ]
      addresses = dev.config.get("addresses")
      if addresses:
        dev_config.append({"addresses": format_addresses(addresses)})
        pass
      ethernets.append( { dev.device_name: dev_config } )
      pass
    elif dev.config["device_type"] == "wifi":
      wifis.append({ dev.device_name: [ { 'dhcp4': dev.config["dhcp4"] },
                                        { 'optional': dev.config["dhcp4"] },
                                        { 'access-points': dev.config["access-points"] } ] })
      pass

    bond = dev.config.get("bond")
    if bond:
      bond_device = bond["device_name"]
      this_bond = bonds.get(bond_device)
      if this_bond:
        this_bond["interfaces"].append(dev.device_name)
      else:
        this_bond = { 
          "interfaces": [dev.device_name],
          "addresses": bond["addresses"]
        }
        bonds[bond_device] = this_bond
        pass
      pass
    pass

  bonds2 = []
  for bond_device in bonds.keys():
    bond = bonds[bond_device]
    bonds2.append( [ { bond_device:
                       [ {"interfaces": "[ " + ", ".join(bond["interfaces"]) + " ]",
                          "addresses": format_addresses(bond["addresses"]) } ] } ] )
    pass

  if ethernets:
    ifdecl.append( {'ethernets': ethernets } )
    pass
  if bonds2:
    ifdecl.append( {'bonds': bonds2 })
    pass
  if wifis:
    ifdecl.append( {'wifis': wifis} )
    pass

  netplan = [ '# This file is auto-generated by wce triage lib/netplan.py.',
              {"network": ''},
              ifdecl ]

  if filename:
    output = open(filename, "w")
  else:
    output = sys.stdout
    pass

  printer = Printer( output )
  printer.print_tree(netplan, 0)
  pass


def generate_ap_param():
  """ generate access-point param."""
  SSID = os.environ.get('TRIAGE_SSID', 'wcetriage')
  WIFIPASSWORD = os.environ.get('TRIAGE_PASSWORD', 'thepasswordiswcetriage')

  if len(SSID) > 0 and len(WIFIPASSWORD) > 0:
    return { SSID: [ {"password": WIFIPASSWORD } ] }
    pass
  return {}


def generate_default_config(devices):
  """generates the default config for network devices and set it to the
  device.config.
  Note that the shape of config is flat and different from netplan printer.
"""

  ethernets = []
  wifis = []
  
  WCE_SERVER = os.environ.get(const.WCE_SERVER, 'false')

  # Uber-default interface setup
  for dev in devices:
    if dev.device_type == NetworkDeviceType.Ethernet:
      dev.set_config({ "device_type": "ethernet",
                       "dhcp4": 'yes',
                       'optional': 'yes' })
      ethernets.append(dev)
    elif dev.device_type == NetworkDeviceType.Wifi:
      # netplan works with wpa-supplicant, generates a simple config file
      # in the same directory and hands off the auth.
      dev.set_config({ "device_type": "wifi",
                       'dhcp4': 'yes',
                       'optional': 'yes',
                       'access-points': [generate_ap_param()]})
      wifis.append(dev)
      pass
    pass

  # Redo default for server
  if WCE_SERVER == "true":
    if len(ethernets) >= 2:
      for eth in ethernets:
        eth.set_config({ "device_type": "ethernet",
                         'dhcp4': 'no',
                         'optional': 'yes',
                         "bond": { "device_name": "bond0",
                                   "addresses": [ ("10.3.2.1", 24) ] } })
        pass
      pass
    else:
      for eth in ethernets:
        eth.set_config({ "device_type": "ethernet",
                         'dhcp4': 'no',
                         'optional': 'yes',
                         "addresses": [ ("10.3.2.1", 24) ]})
        pass
      pass
    pass
  pass

#
_network_id = None
def generate_network_id(devices):
  """generates an unique ID for particular machine."""
  global _network_id
  if _network_id is not None:
    return _network_id
  
  machine_id = None
  try:
    with open("/etc/ssh/ssh_host_rsa_key.pub") as ssh_key:
      machine_id = ssh_key.read().encode("iso-8859-1")
      pass
  except FileNotFoundError:
    # This means ssh server is not installed.
    netdir = "/sys/class/net"
    for netdev in os.listdir(netdir):
      if netdev == "lo":
        continue
      netaddrpath = os.path.join(netdir, netdev, "address")
      try:
        with open(netaddrpath) as macaddrfile:
          macaddr = macaddrfile.read().encode("iso-8859-1").strip()
          if macaddr == "00:00:00:00:00:00":
            continue
          machine_id = macaddr
          break
        pass
      except FileNotFoundError:
        pass
      pass
    pass
    
  device_names = []
  for device in devices:
    device_names.append(device.device_name)
    pass
  _network_id = hashlib.sha1(machine_id + " ".join(sorted(device_names)).encode('iso-8859-1')).hexdigest()
  return _network_id

  
def save_network_config(config_dir, devices):
  """saves network device config"""
  network_id = generate_network_id(devices)

  configs = []
  for device in devices:
    configs.append((device.device_name, device.config))
    pass

  config_filename = ".netplan_" + network_id
  with open(os.path.join(config_dir, config_filename), "w") as cfg:
    json.dump({ "id": network_id, "configs": configs}, cfg, indent=2)
    pass
  pass

def load_network_config(config_dir, devices):
  """loads network device config, if the config file is available."""
  network_id = generate_network_id(devices)
  config_filename = ".netplan_" + network_id

  config_filepath = os.path.join(config_dir, config_filename)
  if not os.path.exists(config_filepath):
    return False

  device_map = {}
  for device in devices:
    device_map[device.device_name] = device
    pass

  try:
    with open(config_filepath, "r") as cfg:
      dev_configs = json.load(cfg)
      if network_id == dev_configs["id"]:
        for device_name, config in dev_configs["configs"]:
          device = device_map.get(device_name)
          if device:
            device.set_config(config)
            pass
          pass
        pass
      pass
    pass
  except:
    return False
  
  # Update the WIFI connection if provided.
  ap_param = generate_ap_param()
  if ap_param:
    for device in devices:
      if device.device_type == NetworkDeviceType.Wifi:
        config = device.config
        if config:
          config['access-points'] = [ap_param]
          device.set_config(config)
          pass
        pass
      pass
    pass
  return True


if __name__ == "__main__":
  os.environ["TRIAGE_SSID"] = "fakessid"
  os.environ["TRIAGE_PASSWORD"] = "fake-password"

  eth0 = NetworkDevice(device_name="eth0", device_type=NetworkDeviceType.Ethernet)
  eth1 = NetworkDevice(device_name="eth1", device_type=NetworkDeviceType.Ethernet)
  eth2 = NetworkDevice(device_name="eth2", device_type=NetworkDeviceType.Wifi)
  netdevs = [eth0, eth1, eth2]

  os.environ[const.WCE_SERVER] = 'false'

  generate_default_config(netdevs)
  generate_netplan_file(None, netdevs)

  os.environ[const.WCE_SERVER] = 'true'

  generate_default_config(netdevs)
  generate_netplan_file(None, netdevs)

  netdevs = [eth0]
  generate_default_config(netdevs)
  generate_netplan_file(None, netdevs)

  netdevs = [eth0, eth1, eth2]
  eth0.set_config(None)
  eth1.set_config(None)
  eth2.set_config(None)

  os.environ[const.WCE_SERVER] = 'false'
  generate_default_config(netdevs)

  eth1.config["optional"] = "no"
  save_network_config("/tmp", netdevs)

  eth0.set_config(None)
  eth1.set_config(None)
  eth2.set_config(None)
  load_network_config("/tmp", netdevs)
  generate_netplan_file(None, netdevs)

  pass
