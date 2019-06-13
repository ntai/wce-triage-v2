#!/usr/bin/env python3
#
# This script is intended to run by wce triage service.
# In other word, this is executed as root.
#
# When the service starts, 
#
import os, sys, subprocess
import * from components.network
import * from lib.netplan

devices = detect_ethernet(run_ip_command())
subprocess.call('mkdir -p /run/netplan', shell=True)
create_netplan_cfg('/run/netplan/triage.yaml', devices)
subprocess.call('netplan apply')
sys.exit(0)
