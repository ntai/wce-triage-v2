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
from ..lib.network_manager import is_network_manager_on, connect_to_triage_wifi

if __name__ == "__main__":
  subprocess.call('mkdir -p /run/netplan', shell=True)

  if is_network_manager_on():
    # generate_netplan_file_for_network_manager()
    connect_to_triage_wifi()
  else:
    devices = detect_net_devices()
    if not load_network_config("/etc/netplan", devices):
      generate_default_config(devices)
      pass
    generate_netplan_file('/run/netplan/triage.yaml', devices)
    subprocess.call('netplan generate', shell=True)
    subprocess.call('netplan apply', shell=True)
    pass
  sys.exit(0)
  pass
