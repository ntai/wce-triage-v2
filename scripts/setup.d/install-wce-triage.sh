#!/bin/sh

if [ "x${TRIAGEUSER}" = "x" ] ; then
    TRIAGEUSER=triage
fi
#
# Now the triage http server service that produces the triage output
#
cat > /tmp/wce-triage.service <<EOF
[Unit]
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
EOF

sudo install -m 0755 /tmp/wce-triage.service /etc/systemd/system/wce-triage.service

cat > /tmp/wce-triage.sh <<EOF
#!/bin/bash
#
python3 -m wce_triage.bin.start_network
cd /usr/local/share/wce/wce-triage-ui
python3 -m wce_triage.http.httpserver
EOF

sudo install -m 0555 /tmp/wce-triage.sh /usr/local/bin

sudo systemctl daemon-reload

if [ x$WCE_TRIAGE_DISK = xtrue ] ; then
sudo systemctl enable wce-triage.service
else
sudo systemctl disable wce-triage.service
fi
