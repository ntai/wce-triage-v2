#!/usr/bin/python3
import os, subprocess

TRIAGEUSER=os.environ.get("TRIAGEUSER", "triage")

subprocess.run('sudo rm -f /tmp/wce-kiosk.sh /tmp/wce-kiosk.service /tmp/wce-triage.service', shell=True)

#
# X11 has to run as root, and chrome has to run as triage.
#
wce_kiosk_sh = open('/tmp/wce-kiosk.sh', 'w')
wce_kiosk_sh.write('''#!/bin/bash
xset -dpms
xset s off
xhost + localhost SI:localuser:{U}
sudo -H -u {U} DISPLAY=$DISPLAY openbox-session &
sudo -H -u {U} DISPLAY=$DISPLAY start-pulseaudio-x11
BROWSER=/usr/bin/chromium-browser
if [ ! -x $BROWSER ] ; then
  BROWSER=/usr/bin/google-chrome
fi
while true; do
  sleep 1
  if lsof -Pi :8312 -sTCP:LISTEN -t >/dev/null ; then
      sudo -H -u {U} DISPLAY=$DISPLAY xbacklight -set 90
      sudo -H -u {U} DISPLAY=$DISPLAY pactl set-sink-mute 0 false
      sudo -H -u {U} DISPLAY=$DISPLAY pactl set-sink-volume 0 90%
      sudo -H -u {U} rm -rf /home/{U}/.{{config,cache}}/{{google-chrome,chromium}}/
      sudo -H -u {U} $BROWSER --display=$DISPLAY --kiosk --no-first-run 'http://localhost:8312'
  fi
  sleep 1
done
'''.format(U=TRIAGEUSER))
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

subprocess.run(['sudo', '-H', 'install', '-m', '0644', '/tmp/wce-kiosk.service', '/etc/systemd/system/wce-kiosk.service'])

subprocess.run(['sudo', 'systemctl', 'daemon-reload'])
subprocess.run(['sudo', 'systemctl', 'enable', 'wce-kiosk.service'])
