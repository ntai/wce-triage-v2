#!/usr/bin/python3

import os, sys

os.environ['GRUB_DISABLE_OS_PROBER'] = 'true'
os.environ['TRIAGEUSER'] = 'wce'
os.environ['TRIAGEPASS'] = 'wce123'
os.environ['WCE_DESKTOP'] = 'true'
os.environ['PATCHES'] = 'desktop'

if __name__ == "__main__":
  steps = ['install_packages',
           # Create triage account
           'config_triage_user',
           # Install triage software and services
           'install_assets',
           # patch up system and boot loader installation
           'patch_system',
  ]
  
  for step in steps:
    package_name = 'wce_triage.setup.' + step
    subprocess.run(['sudo', '-H', 'python3', '-m', package_name])
    pass
  pass
