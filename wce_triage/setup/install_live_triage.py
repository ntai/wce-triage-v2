#!/usr/bin/python3
#
# This is for Triage USB stick on mini system
#
import os, sys, subprocess, stat

if __name__ == "__main__":
  LIVE_TRIAGE="/LIVE-TRIAGE"
  live_triage_script = open('/tmp'+LIVE_TRIAGE, "w")
  live_triage_script.write('''#!/bin/sh
cat > /tmp/get-mount-point.py << EOF
import os, sys, re

def match(mount_roots, path):
    criteria = path.split('/')
    for c_len in range(len(criteria), 0, -1):
        candidate = '/'.join(criteria[:c_len])
        found = mount_roots.get(candidate)
        if found:
            return found
        pass
    return ''

if __name__ == "__main__":

    mount_re = re.compile('([^ ]+)\s+([^ ]+)\s+([^ ]+)\s+([^ ]+)\s+([^ ]+)\s+([^ ]+)')
    mount_roots = {}

    with open('/proc/mounts') as mounts_fd:
        for mount_entry in mounts_fd.read().splitlines():
            matched = mount_re.match(mount_entry)
            if matched:
                mount_roots[matched.group(2)] = matched.group(2)
                pass
            pass
        pass

    path = sys.argv[1]
    if path[0] == '.':
      path = os.getcwd()
      pass
    print(match(mount_roots, path))
    pass
EOF
MOUNTPOINT=$(python3 /tmp/get-mount-point.py pwd)

x-www-browser http://localhost:8312 &

export PYTHONPATH=$MOUNTPOINT/usr/local/lib/python3.6/dist-packages/:$MOUNTPOINT/usr/lib/python3/dist-packages/

cd $MOUNTPOINT/usr/local/share/wce/wce-triage-ui
pkexec env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY PYTHONPATH=$PYTHONPATH python3 -m wce_triage.http.httpserver 
''')
  live_triage_script.close()

  subprocess.run(['sudo', '-H', 'install', '-m', '0755', '/tmp'+LIVE_TRIAGE, LIVE_TRIAGE])
  pass
