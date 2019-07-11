#!/usr/bin/python3


import os, sys, subprocess

TRIAGEUSER=os.environ.get("TRIAGEUSER", "triage")

if __name__ == "__main__":

  subprocess.run('sudo rm /swapfile', shell=True)

  os.environ['TRIAGE_SSID'] = 'wcetriage'
  os.environ['TRIAGE_PASSWORD'] = 'thepasswordiswcetriage'

  subprocess.run('sudo python3 wce_triage.bin.start_network', shell=True)
  subprocess.run('sudo apt install -y python3-pip', shell=True)
  subprocess.run('sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage', shell=True)

  subprocess.run('sudo apt purge g++-7', shell=True)
  subprocess.run('sudo apt purge wamerican wbritish', shell=True)
  subprocess.run('sudo apt purge manpages-dev', shell=True)

  subprocess.run('sudo apt purge linux-headers-generic', shell=True)
  subprocess.run('sudo apt purge linux-headers-4.15.0-52', shell=True)
  subprocess.run('sudo linux-headers-4.15.0-52-generic', shell=True)
  pass

