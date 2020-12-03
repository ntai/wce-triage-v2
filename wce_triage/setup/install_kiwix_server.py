#!/usr/bin/python3

import os, subprocess

kiwix_services = [
  "kiwix-server-proxy.socket",
  "kiwix-server-proxy.service",
  "kiwix-server.socket",
  "kiwix-server.service",
]

def install_systemd_file(SYSTEMD_FILE):
  """instead of copying, this makes symbolic link """
  destination = os.path.join("/etc/systemd/system", SYSTEMD_FILE)
  if not os.path.exists(destination):
    subprocess.call(f"sudo -H ln -s /usr/local/share/wce/lib/systemd/system/{SYSTEMD_FILE} {destination}", shell=True)
    pass

  subprocess.call(f"sudo -H systemctl enable {SYSTEMD_FILE}", shell=True)
  pass


if __name__ == "__main__":
  for filename in kiwix_services:
    install_systemd_file(filename)
    pass
  pass
