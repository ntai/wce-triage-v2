#!/usr/bin/env python3
#
# This script is intended to run by wce triage service.
# In other word, this is executed as root.
#
# When the service starts, 
#
import os, sys, subprocess
sys.path.append(os.path.join("../wce_triage"))
from components.network import * 
from lib.netplan import *

if __name__ == "__main__":
  devices = detect_net_devices()
  subprocess.call('mkdir -p /run/netplan', shell=True)
  create_netplan_cfg('/run/netplan/triage.yaml', devices)
  subprocess.call('netplan generate', shell=True)
  subprocess.call('netplan apply', shell=True)
  sys.exit(0)
  pass

