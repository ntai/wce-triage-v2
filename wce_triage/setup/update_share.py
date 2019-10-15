#!/usr/bin/python3

import os, sys, subprocess
env = os.environ.copy()

if __name__ == "__main__":
  this_dir = os.path.dirname(__file__)
  src_dir = os.path.join(this_dir, "share/wce/")
  dst_dirs = [ "/usr/local/share/wce/",  "/var/lib/netclient/wcetriage/usr/local/share/wce/", "/var/lib/netclient/wcetriage_amd64/usr/local/share/wce/", "/var/lib/netclient/wcetriage_x32/usr/local/share/wce/" ]
  # dst_dirs = [ "/usr/local/share/wce/"]

  for dst_dir in dst_dirs:
    if os.path.exists(dst_dir) and os.path.isdir(dst_dir):
      print('sudo -E -H rsync -av {} {}'.format(src_dir, dst_dir))
      subprocess.run(['sudo', '-E', '-H', 'rsync', '-av', src_dir, dst_dir], env=env)
      pass
    pass
  pass
