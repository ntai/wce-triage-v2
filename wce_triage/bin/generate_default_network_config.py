#!/usr/bin/env python3
#
# This script is intended to run by wce triage service.
# In other word, this is executed as root.
#
# When the triage service starts, it runs this to generate default network
# setup so that it can do triaging of network device.
#
from ..components.network import detect_net_devices
from ..lib.netplan import generate_default_config, save_network_config

if __name__ == "__main__":
  devices = detect_net_devices()
  generate_default_config(devices)
  save_network_config("/etc/netplan", devices)
  pass

