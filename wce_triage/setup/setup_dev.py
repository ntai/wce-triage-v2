#!/usr/bin/python3
#
# This is to set up a laptop or desktop to be used for
# WCE's disk prep.
#
import os, subprocess
from ..const import const

env = os.environ.copy()
env[const.GRUB_DISABLE_OS_PROBER] = const.true
env[const.TRIAGEUSER] = 'triage'
env[const.TRIAGEPASS] = 'triage'

# Workstation gets all of packages
env[const.WCE_DESKTOP] = const.true
env[const.WCE_TRIAGE_DISK] = const.true
env[const.WCE_SERVER] = const.true

# 
env[const.PATCHES] = const.server
# env[const.PATCHES] = const.workstation

if __name__ == "__main__":
  steps = [#'install_packages',
           # Create triage account
           # 'config_triage_user',
           # Install triage software and services
           # 'install_assets',
           # patch up system, install /usr/local/bin files and boot loader installation
           #'patch_system',
           # 'install_boot',
           #
           #'install_pxeboot',
  ]
  
  for step in steps:
    package_name = 'wce_triage.setup.' + step
    subprocess.run(['sudo', '-E', '-H', 'python3', '-m', package_name], env=env)
    pass

  # disable auto mount
  pass
