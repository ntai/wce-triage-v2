#!/usr/bin/python3
import os, subprocess

TRIAGEUSER=os.environ.get("TRIAGEUSER", "triage")

subprocess.run('sudo rm -f /tmp/wce-kiosk.sh /tmp/wce-kiosk.service /tmp/wce-triage.service', shell=True)

#
# X11 has to run as root, and chrome has to run as triage.
#
wce_kiosk_sh = open('/tmp/wce-kiosk.sh', 'w')
wce_kiosk_sh.write('''#!/bin/bash

LOGFILE=/tmp/kiosk.log
set > $LOGFILE
chmod 666 $LOGFILE

export BROWSER=/usr/bin/firefox

xset -dpms
xset s off
cp /root/.Xauthority /home/triage/.Xauthority
chown triage:triage /home/triage/.Xauthority
export XAUTHORITY=/home/triage/.Xauthority
xhost + localhost SI:localuser:triage

echo "openbox" >> $LOGFILE
sudo -H -u triage -g triage openbox-session >> $LOGFILE 2>&1 &
echo "pulseaudio" >> $LOGFILE
# sudo -H -u triage -g triage start-pulseaudio-x11 >> $LOGFILE 2>&1
sudo -H -u triage -g triage pulseaudio --start >> $LOGFILE 2>&1
echo "xbacklight" >> $LOGFILE
sudo -H -u triage -g triage xbacklight -set 90 >> $LOGFILE 2>&1
echo "pactl" >> $LOGFILE
sudo -H -u triage -g triage pactl set-sink-mute 0 false >> $LOGFILE 2>&1
sudo -H -u triage -g triage pactl set-sink-volume 0 90% >> $LOGFILE 2>&1

echo "waiting for triage server" >> $LOGFILE

while ! wget -T 1 -O /dev/null -q http://localhost:8312/version.json; do
  sleep 1
done

echo "starting browser" >> $LOGFILE
sleep 3
sudo -H -u triage -g triage $BROWSER --display=$DISPLAY --kiosk 'http://localhost:8312' >> $LOGFILE 2>&1
echo "browser started" >> $LOGFILE

while wget -T 1 -O /dev/null -q http://localhost:8312/version.json; do
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
After=snapd.service
Wants=network.target sound.target network-online.target
Requires=wce-triage.service
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
subprocess.run(['sudo', 'systemctl', 'enable', 'wce-triage.service'])
