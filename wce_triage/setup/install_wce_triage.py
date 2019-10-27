#!/usr/bin/python3

import os, sys, subprocess

tmpfile = '/tmp/wce-triage.sh'

wce_triage_sh = open(tmpfile, 'w')
wce_triage_sh.write('''#!/bin/bash
#
python3 -m wce_triage.bin.start_network
cd /usr/local/share/wce/wce-triage-ui
python3 -m wce_triage.http.httpserver
''')
wce_triage_sh.close()

subprocess.run(['sudo', '-H', 'install', '-m', '0555', tmpfile, '/usr/local/bin'])

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

subprocess.run(['sudo', '-H', 'install', '-m', '0644', '/tmp/wce-triage.service', '/etc/systemd/system/wce-triage.service'])

subprocess.run(['sudo', 'systemctl', 'daemon-reload'])
subprocess.run(['sudo', 'systemctl', 'enable', 'wce-kiosk.service'])
