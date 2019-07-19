#!/usr/bin/python3

import os, sys

env = os.environ.copy()

env['GRUB_DISABLE_OS_PROBER'] = 'true'
env['TRIAGEUSER'] = 'wce'
env['TRIAGEPASS'] = 'wce123'
env['WCE_DESKTOP'] = 'true'
env['PATCHES'] = 'desktop'

if __name__ == "__main__":
  steps = ['install_packages',
           # Create triage account
           'config_triage_user',
           # Install triage software and services
           'install_assets',
           # patch up system and boot loader installation
           'patch_system'
  ]
  
  for step in steps:
    package_name = 'wce_triage.setup.' + step
    subprocess.run(['sudo', '-E', '-H', 'python3', '-m', package_name], env=env)
    pass
  pass
