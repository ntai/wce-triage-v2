#!/usr/bin/python3
#
# This is for setting up network server
#
import os, sys, subprocess

# For the setup user 
os.environ['TRIAGEUSER'] = 'triage'
os.environ['TRIAGEPASS'] = 'triage'

# This affects the package installation
os.environ['WCE_SERVER'] = 'true'

# This affects patch_system
os.environ['PATCHES'] = 'server'

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

