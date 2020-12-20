#!/usr/bin/python3
#
# This is to set up a laptop or desktop to be used for
# WCE's disk prep.
#
import os, subprocess
from ..const import const

env = os.environ.copy()
env[const.GRUB_DISABLE_OS_PROBER] = 'true'
env[const.TRIAGEUSER] = 'wce'
env[const.TRIAGEPASS] = 'wce123'

# Workstation gets all of packages
env[const.WCE_DESKTOP] = 'true'
env[const.WCE_TRIAGE_DISK] = 'true'
env[const.WCE_SERVER] = 'true'

# 
env[const.PATCHES] = 'workstation'

if __name__ == "__main__":
  steps = ['install_packages',
           # Create triage account
           'config_triage_user',
           # Install triage software and services
           'install_assets',
           # patch up system, install /usr/local/bin files and boot loader installation
           'patch_system',
           'install_boot',
           #
           'install_pxeboot',
           #
           'configure_lighttpd'
  ]
  
  for step in steps:
    package_name = 'wce_triage.setup.' + step
    subprocess.run(['sudo', '-E', '-H', 'python3', '-m', package_name], env=env)
    pass

  # disable auto mount
  subprocess.run('gsettings set org.mate.media-handling automount false', shell=True)
  subprocess.run('gsettings set org.gnome.desktop.media-handling automount false', shell=True)
  pass
