#!/usr/bin/python3

import os

from . import sudo_run_module

env = os.environ.copy()

env['GRUB_DISABLE_OS_PROBER'] = 'true'
env['TRIAGEUSER'] = 'wce'
env['TRIAGEPASS'] = 'wce123'
env['WCE_DESKTOP'] = 'true'
env['PATCHES'] = 'desktop'

if __name__ == "__main__":
  steps = ['install_packages',
           # SDL2+GLEW applications need Xwayland. Runs after the packages
           # are in, since it looks at what actually got installed.
           'patch_wayland',
           # Create triage account
           'config_triage_user',
           # Install triage software and services
           'install_assets',
           # patch up system and boot loader installation
           'patch_system',
           # Install kiwix server
           'install_kiwix_server'
  ]
  
  for step in steps:
    package_name = 'wce_triage.setup.' + step
    sudo_run_module(package_name, env)
    pass
  pass
