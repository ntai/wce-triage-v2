#!/bin/sh


if [ "x${TRIAGEUSER}" = "x" ] ; then
    TRIAGEUSER=triage
fi

#
# X11 has to run as root, and chrome has to run as triage.
#
cat > /tmp/wce-kiosk.sh <<EOF
#!/bin/bash
xset -dpms
xset s off
xhost + localhost SI:localuser:$TRIAGEUSER
sudo -H -u $TRIAGEUSER DISPLAY=$$DISPLAY openbox-session &
sudo -H -u $TRIAGEUSER DISPLAY=$$DISPLAY start-pulseaudio-x11
while true; do
  sudo -H -u $TRIAGEUSER rm -rf /home/triage/.{config,cache}/google-chrome/
  sudo -H -u $TRIAGEUSER google-chrome --display=$$DISPLAY --kiosk --no-first-run 'http://localhost:8312'
done
EOF

sudo install -m 0555 /tmp/wce-kiosk.sh /usr/local/bin

#
# 
#
cat > /tmp/wce-kiosk.service <<EOF
[Unit]
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
EOF

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

subprocess.run([sudo', 'install', '-m', '0755', '/tmp/wce-triage.service', '/etc/systemd/system/wce-triage.service'])
subprocess.run(['sudo', 'systemctl', 'daemon-reload'])
subprocess.run(['sudo', 'systemctl', 'enable', 'wce-triage.service'])


sudo install -m 0755 /tmp/wce-kiosk.service /etc/systemd/system/wce-kiosk.service
sudo systemctl daemon-reload
sudo systemctl enable wce-kiosk.service
