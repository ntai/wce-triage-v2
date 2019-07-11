#!/usr/bin/python3
#
import os, sys, subprocess

TRIAGEUSER=os.environ.get("TRIAGEUSER", "triage")

if __name__ == "__main__":
  subprocess.call('sudo -H mkdir -p /usr/local/share/wce', shell=True)
  subprocess.call('sudo -H mkdir -p /usr/local/share/wce/wce-triage-ui', shell=True)
  subprocess.call('sudo -H chown {user}:{user} /usr/local/share/wce/wce-triage-ui'.format(user=TRIAGEUSER), shell=True)
  subprocess.call('sudo -H mkdir -p /usr/local/share/wce/triage/bin', shell=True)
  subprocess.call('sudo -H mkdir -p /usr/local/share/wce/triage/assets', shell=True)
  subprocess.call('sudo -H mkdir -p /usr/local/share/wce/ubuntu-packages', shell=True)
  subprocess.call('sudo -H chown $TRIAGEUSER:$TRIAGEUSER /usr/local/share/wce/ubuntu-packages', shell=True)

  os.chdir('/usr/local/share/wce/ubuntu-packages')

  subprocess.call('apt download grub-efi-amd64', shell=True, stderr=subprocess.PIPE)

  apt = subprocess.run('apt search -q xserver-xorg-video-nvidia', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  for line in apt.stdout.decode('iso-8859-1').splitlines():
    line = line.strip()
    if 'xserver-xorg-video-nvidia' in line:
      driver_name = line.split('/')[0]
      pass
  print ("nVidia driver " + driver_name)
  subprocess.call('apt download ' + driver_name, shell=True)

  # Create default update script.
  # If download succeeds, the updated update-wce-triage would run.
  # At minimum, the UI and wce_triage package needs to be updated.
  # When the UI distribution method changes, this might change.

  os.chdir('/usr/local/share/wce/triage/bin')

  update_triage = open('/tmp/update-wce-triage', 'w')
  update_triage.write('''#!/bin/sh
sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage
cd /usr/local/share/wce/wce-triage-ui
wget -q -O - http://release.cleanwinner.com/wce/wce-triage-ui.tgz | tar xzf -
''')
  update_triage.close()

  subprocess.call('sudo -H install -m 555 /tmp/update-wce-triage /usr/local/share/wce/triage/bin', shell=True)

  subprocess.call('wget -q -O - http://release.cleanwinner.com/wce/update-wce-triage && chmod +x update-wce-triage', shell=True)
  #
  subprocess.call('sh ./update-wce-triage', shell=True)
  pass
