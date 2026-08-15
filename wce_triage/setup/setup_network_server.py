#!/usr/bin/python3
#
# This is for setting up network server
#
import os, subprocess
from ..const import const
from . import sudo_run_module

# For the setup user 
env = os.environ.copy()
env['TRIAGEUSER'] = 'triage'
env['TRIAGEPASS'] = 'triage'

# This affects the package installation
env[const.WCE_SERVER] = 'true'

# This affects patch_system
env[const.PATCHES] = const.server

if __name__ == "__main__":
  
  steps = ['install_packages',
           #
           'configure_lighttpd'

           # Create triage account
           'config_triage_user',
           # Install triage software and services
           'install_assets',
           # patch up system and boot loader installation
           'patch_system',
           'install_boot',
           'install_pxeboot'
  ]
  
  for step in steps:
    package_name = 'wce_triage.setup.' + step
    sudo_run_module(package_name, env)
    pass
  pass

