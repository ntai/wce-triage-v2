#!/usr/bin/python3
#
# This is for Triage USB stick on mini system
#
# This sets up the USB stick after installing mini.iso
#

import os, sys, subprocess

os.environ['GRUB_DISABLE_OS_PROBER'] = 'true'
os.environ['TRIAGEUSER'] = 'wce'
os.environ['WCE_DESKTOP'] = 'true'

if __name__ == "__main__":
  
  steps = ['install_packages',
           # Create triage account
           'setup_triage_user',
           # Install Google Chrome
           'install_chrome',
           # patch up the system
           'patch_system',
           # Install triage software and services
           'install_assets',
           'install_wce_triage',
           'install_wce_kiosk',
           # boot loader installation
           'install_boot'
  ]
  
  # Install Ubunto packages (some are python packages)
  for step in steps:
    package_name = 'wce_triage.setup.' + step
    subprocess.run(['sudo', '-H', 'python3', '-m', package_name])
    pass
  pass

