#!/usr/bin/python3

import os, sys, subprocess

wce_triage_sh = open('/tmp/wce-triage.sh', 'w')
wce_triage_sh.write('''#!/bin/bash
#
python3 -m wce_triage.bin.start_network
cd /usr/local/share/wce/wce-triage-ui
python3 -m wce_triage.http.httpserver
''')
wce_triage_sh.close()

subprocess.run(['sudo', '-H', 'install', '-m', '0555', '/tmp/wce-triage.sh', '/usr/local/bin'])

