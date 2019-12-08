#!/usr/bin/python3


import os, subprocess

TRIAGEUSER=os.environ.get("TRIAGEUSER", "triage")

if __name__ == "__main__":

  # USB stick is going to run with union-fs and using swapfile is harmful.
  if os.path.exists('/swapfile'):
    subprocess.run('sudo rm /swapfile', shell=True)
    pass

  env = os.environ.copy()
  env['TRIAGE_SSID'] = 'wcetriage'
  env['TRIAGE_PASSWORD'] = 'thepasswordiswcetriage'

  subprocess.run(['sudo', '-E', '-H', 'python3', '-m', 'wce_triage.bin.start_network'], env=env)
  # yes, this was a shell script...
  subprocess.run('sudo apt install -y python3-pip', shell=True)
  subprocess.run('sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage', shell=True)

  subprocess.run('sudo apt purge g++-7', shell=True)
  subprocess.run('sudo apt purge wamerican wbritish', shell=True)
  subprocess.run('sudo apt purge manpages-dev', shell=True)

  subprocess.run('sudo apt purge linux-headers-generic', shell=True)
  subprocess.run('sudo apt purge linux-headers-4.15.0-52', shell=True)
  subprocess.run('sudo linux-headers-4.15.0-52-generic', shell=True)
  pass

