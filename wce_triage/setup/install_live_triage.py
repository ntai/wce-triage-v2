#!/usr/bin/python3
#
# This is for Triage USB stick on mini system
#
import os, sys, subprocess, stat

if __name__ == "__main__":
  LIVE_TRIAGE="wce-live-triage"
  tmp_live_triage = "/tmp/"+LIVE_TRIAGE
  real_live_triage = "/usr/local/bin/"+LIVE_TRIAGE

  live_triage_script = open(tmp_live_triage, "w")
  live_triage_script.write('''#!/usr/bin/env python3 
import os, sys, re, subprocess, traceback, time
import urllib.request
import urllib.error

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
             mountpoint + "/usr/lib/python3/dist-packages"]
    if pythonpath:
        paths = paths + pythonpath.split(':')
        pass
    os.environ["PYTHONPATH"] = ":".join(paths)
        
    ui_dir = mountpoint + "/usr/local/share/wce/wce-triage-ui"
    cmd0 = "pkexec env DISPLAY={display} XAUTHORITY={xauth} PYTHONPATH={pythonpath} python3 -m wce_triage.http.httpserver --live-triage --rootdir={rootdir} --wcedir={wcedir}"
    cmd1 = cmd0.format(display=os.environ.get('DISPLAY'),
                       xauth=os.environ.get('XAUTHORITY'),
                       pythonpath=os.environ.get('PYTHONPATH'),
                       rootdir=mountpoint + "/usr/local/share/wce/wce-triage-ui",
                       wcedir=mountpoint + "/usr/local/share/wce")
    subprocess.Popen(cmd1, shell=True, cwd=ui_dir)

    while True:
        try:
            with urllib.request.urlopen('http://localhost:8312/dispatch/triage.json') as res:
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
    
    subprocess.Popen("x-www-browser http://localhost:8312", shell=True)
    pass
''')
  live_triage_script.close()

  subprocess.run(['sudo', '-H', 'install', '-m', '0755', tmp_live_triage, real_live_triage])
  subprocess.run(['sudo', '-H', 'ln', '-s', real_live_triage, "/autorun"])
  pass

