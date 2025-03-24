#!/usr/bin/python3
#
# This is for Triage USB stick on mini system
#
# This sets up the USB stick after installing mini.iso
#

import os, subprocess
from . import get_ubuntu_release

env = os.environ.copy()

env['WCE_TRIAGE_DISK'] = 'true'
env['GRUB_DISABLE_OS_PROBER'] = 'true'
env['TRIAGEUSER'] = 'triage'
env['TRIAGEPASS'] = 'triage'
env['PATCHES'] = 'triage'

if __name__ == "__main__":
  ubuntu_release = get_ubuntu_release()
  
  steps = ['install_packages',
           # Create triage account
           'config_triage_user',
           # Install Google Chrome - deprecated in favor of firefox
           # 'install_chrome',
           # Install triage software and services
           'install_assets',
           ('install_wce_triage', ["18.04", "20.04", "22.04"]),
           ('install_wce_kiosk' ["18.04", "20.04", "22.04"]),
           # Install non-snap (aka pkg) Firefox
           'install_firefox',
           'install_sound',
           'install_live_triage',
           # patch up system and boot loader installation
           ('patch_system',  ["18.04", "20.04", "22.04"]),
           'install_boot',
           'cleanup_installation',
  ]
  
  # Install Ubunto packages (some are python packages)
  for step in steps:
    if isinstance(step, str):
      package_name = 'wce_triage.setup.' + step
    else:
      step_name, releases = step
      if ubuntu_release not in releases:
        continue
      package_name = 'wce_triage.setup.' + step_name
    subprocess.run(['sudo', '-E', '-H', 'python3', '-m', package_name], env=env)
    pass

  # Don't run periodical updates for triage.
  # It is really bad if the updates run during triaging process.
  
  dailies = [
    'apt-daily.timer',
    'apt-daily.service',
    'apt-daily-upgrade.timer',
    'apt-daily-upgrade.service' ]

  for daily in dailies:
    args = ['systemctl', 'disable', daily]
    subprocess.run(args)
    pass

  pass

