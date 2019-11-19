#!/usr/bin/python3
#
# This is for Triage USB stick on mini system
#
# This sets up the USB stick after installing mini.iso
#

import os, subprocess

env = os.environ.copy()

env['WCE_TRIAGE_DISK'] = 'true'
env['GRUB_DISABLE_OS_PROBER'] = 'true'
env['TRIAGEUSER'] = 'triage'
env['TRIAGEPASS'] = 'triage'
env['PATCHES'] = 'triage'

if __name__ == "__main__":
  
  steps = ['install_packages',
           # Create triage account
           'config_triage_user',
           # Install Google Chrome
           'install_chrome',
           # Install triage software and services
           'install_assets',
           'install_wce_triage',
           'install_wce_kiosk',
           'install_live_triage',
           # patch up system and boot loader installation
           'patch_system',
           'install_boot'
  ]
  
  # Install Ubunto packages (some are python packages)
  for step in steps:
    package_name = 'wce_triage.setup.' + step
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

