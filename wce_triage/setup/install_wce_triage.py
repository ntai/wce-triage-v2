#!/usr/bin/python3

import subprocess

tmpfile = '/tmp/wce-triage.sh'

wce_triage_sh = open(tmpfile, 'w')
wce_triage_sh.write('''#!/bin/bash
#
python3 -m wce_triage.bin.start_network
FLASK_ENVIRONMENT=development FLASK_DEBLG=true FLASK_APP=wce_triage.backend.app:create_app flask run --port 8312 --host 0.0.0.0
''')
wce_triage_sh.close()

subprocess.run(['sudo', '-H', 'install', '-m', '0555', tmpfile, '/usr/local/bin'])

#
# Now the triage http server service that produces the triage output
#
wce_triage_service = open('/tmp/wce-triage.service', 'w')
wce_triage_service.write('''[Unit]
Description=WCE Triage service
After=dbus.target snapd.service
StartLimitIntervalSec=0
Wants=network.target sound.target network-online.target

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
