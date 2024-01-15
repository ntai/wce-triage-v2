#!/usr/bin/env python3
import os
import re
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request


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

  path = sys.argv[0]
  if path[0] == '.':
    path = os.getcwd()
    pass
  mountpoint = match(mount_roots, path)
  print("Mount point: " + mountpoint)
  pythonpath = os.environ.get('PYTHONPATH')
  paths = [mountpoint + "/usr/local/lib/python3.6/dist-packages",
           mountpoint + "/usr/local/lib/python3.8/dist-packages",
           mountpoint + "/usr/local/lib/python3.10/dist-packages",
           mountpoint + "/usr/lib/python3/dist-packages"]
  if pythonpath:
    paths = paths + pythonpath.split(':')
    pass
  os.environ["PYTHONPATH"] = ":".join(paths)

  display=os.environ.get('DISPLAY')
  xauth=os.environ.get('XAUTHORITY')
  pythonpath=os.environ.get('PYTHONPATH')
  wcedir=mountpoint + "/usr/local/share/wce"
  flask = wcedir + "/triage/venv/bin/flask"
  if not os.path.exists(flask):
    flask = "flask"
  cmd = ["pkexec", "env", "FLASK_ENVIRONMENT=development", "FLASK_DEBUG=true" ,
         f"FLASK_APP=wce_triage.backend.app:create_app\\(live_triage=True,wcedir=\"{wcedir}\"\\)",
         f"DISPLAY={display}", f"XAUTHORITY={xauth}" f"PYTHONPATH={pythonpath}", flask, "run",
         "--host", "0.0.0.0", "--port", "10600"]
  subprocess.Popen(cmd)

  url = "http://localhost:10600"
  while True:
    try:
      with urllib.request.urlopen(url + '/dispatch/triage') as res:
        html = res.read()
        pass
      break
    except ConnectionRefusedError:
      pass
    except urllib.error.URLError:
      pass
    except Exception:
      print(traceback.format_exc())
      break
    time.sleep(1)
    pass

  subprocess.Popen(f"x-www-browser {url}", shell=True)
  pass
