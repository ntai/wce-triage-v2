#!/usr/bin/python3

import os, subprocess
from wce_triage.setup.install_packages import list_installed_packages


if __name__ == "__main__":
  package = 'curl'
  installed_packages = list_installed_packages()
  if not installed_packages.get(package):
    subprocess.run(['sudo', '-H', 'apt', 'install', '-y', package])
    pass
  os.chdir('/usr/local/share/wce/wce-triage-ui')
  subprocess.run('sudo -H rm -fr /usr/local/share/wce/wce-triage-ui/*', shell=True)
  subprocess.run('cd /usr/local/share/wce/wce-triage-ui && sudo -H curl -L -o - "https://drive.google.com/uc?export=download&id=1eNzcClc_rLebtwhR2KDfZbMA9c9W_P2Y" | tar xzf -', shell=True)
  pass
