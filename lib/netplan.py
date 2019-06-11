
from components.network import NetworkDevice
import sys

spaces = '          '

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

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
            print( "{indent}{key}:".format(indent=spaces[:ilevel*2], key=key), file=self.output )
            self.print_tree(value, ilevel+1)
          else:
            print( "{indent}{key}: {value}".format(indent=spaces[:ilevel*2], key=key, value=value), file=self.output)
            pass
          pass
        pass
      else:
        print(elem, file=self.output)
        pass
      pass
    pass
  pass
      


def create_netplan_cfg(filename, devices):
  ethernets = []
  wifis = []

  for dev in devices:
    if dev.device_type == NetworkDevice.Ethernet:
      ethernets.append( { dev.device_name: [ { 'dhcp4': 'yes' } ] } )
    elif dev.device_type == NetworkDevice.Wifi:
      wifis.append( { dev.device_name: [ { 'dhcp4': 'yes' } ] } )
      pass
    pass

  ifdecl = [ {'version': '2' },
             {'renderer': 'networkd' } ]
  if ethernets:
    ifdecl.append( {'ethernets': ethernets } )
    pass
  if wifis:
    ifdecl.append( {'wifis': wifis} )
    pass

  netplan = [ '# This file is auto-generated.',
              {"network": ''},
              ifdecl ]

  printer = Printer( sys.stdout )
  printer.print_tree(netplan, 0)
  pass


if __name__ == "__main__":
  eth0 = NetworkDevice("eth0", device_type=NetworkDevice.Ethernet)
  eth1 = NetworkDevice("eth1", device_type=NetworkDevice.Ethernet)
  create_netplan_cfg('', [eth0, eth1])
  pass
