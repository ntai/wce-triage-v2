#!/usr/bin/env python3
#
# This script is intended to run by wce triage service.
# In other word, this is executed as root.
#
# When the triage service starts, it runs this to generate default network
# setup so that it can do triaging of network device.
#
import sys, subprocess
from ..components.network import detect_net_devices
from ..lib.netplan import load_network_config, generate_default_config, generate_netplan_file

if __name__ == "__main__":
  netman = subprocess.run('systemctl status -n 0 NetworkManager.service', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  # No need to set up the netplan if Network Manager is available.
  # This means that it's running on a desktop machine with full Ubuntu installation
  if 'NetworkManager.service could not be found' in netman.stderr.decode('iso-8859-1'):
    devices = detect_net_devices()
    subprocess.call('mkdir -p /run/netplan', shell=True)
    if not load_network_config("/etc/netplan", devices):
      generate_default_config(devices)
      pass
    generate_netplan_file('/run/netplan/triage.yaml', devices)
    subprocess.call('netplan generate', shell=True)
    subprocess.call('netplan apply', shell=True)
    pass
  sys.exit(0)
  pass

