#!/usr/bin/python3
#
# This is to set up a laptop or desktop to be used for
# WCE's disk prep.
#
import os, sys, subprocess

env = os.environ.copy()
env['GRUB_DISABLE_OS_PROBER'] = 'true'
env['TRIAGEUSER'] = 'wce'
env['TRIAGEPASS'] = 'wce123'

# Workstation gets all of packages
env['WCE_DESKTOP'] = 'true'
env['WCE_TRIAGE_DISK'] = 'true'
env['WCE_SERVER'] = 'true'

# 
env['PATCHES'] = 'workstation'

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
    subprocess.run(['sudo', '-E', '-H', 'python3', '-m', package_name], env=env)
    pass
  pass
