#!/usr/bin/python3
import os, sys, subprocess

TRIAGEUSER=os.environ.get("TRIAGEUSER", "triage")

#
# X11 has to run as root, and chrome has to run as triage.
#
wce_kiosk_sh = open('/tmp/wce-kiosk.sh', 'w')
wce_kiosk_sh.write('''#!/bin/bash
xset -dpms
xset s off
xhost + localhost SI:localuser:$TRIAGEUSER
sudo -H -u $TRIAGEUSER DISPLAY=$$DISPLAY openbox-session &
sudo -H -u $TRIAGEUSER DISPLAY=$$DISPLAY start-pulseaudio-x11
while true; do
  sudo -H -u $TRIAGEUSER rm -rf /home/triage/.{config,cache}/google-chrome/
  sudo -H -u $TRIAGEUSER google-chrome --display=$$DISPLAY --kiosk --no-first-run 'http://localhost:8312'
  sleep 1
done
''')
wce_kiosk_sh.close()

subprocess.run('sudo install -m 0555 /tmp/wce-kiosk.sh /usr/local/bin', shell=True)

#
# 
#
wce_kiosk_service = open('/tmp/wce-kiosk.service', 'w')
wce_kiosk_service.write('''[Unit]
Description=WCE Kiosk Web Browser
After=dbus.target network.target sound.target network-online.target wce-triage.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=30
User=root
ExecStart=/usr/bin/startx /etc/X11/Xsession /usr/local/bin/wce-kiosk.sh --

[Install]
WantedBy=multi-user.target
''')
wce_kiosk_service.close()

subprocess.run(['sudo', '-H', 'install', '-m', '0755', '/tmp/wce-kiosk.service', '/etc/systemd/system/wce-kiosk.service'])

#
# Now the triage http server service that produces the triage output
#
wce_triage_service = open('/tmp/wce-triage.service', 'w')
wce_triage_service.write('''[Unit]
Description=WCE Triage service
After=dbus.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User=root
ExecStart=/usr/local/bin/wce-triage.sh

[Install]
WantedBy=multi-user.target
''')
wce_triage_service.close()

subprocess.run(['sudo', '-H', 'install', '-m', '0755', '/tmp/wce-triage.service', '/etc/systemd/system/wce-triage.service'])
subprocess.run(['sudo', 'systemctl', 'daemon-reload'])
subprocess.run(['sudo', 'systemctl', 'enable', 'wce-triage.service'])
subprocess.run(['sudo', 'systemctl', 'enable', 'wce-kiosk.service'])
