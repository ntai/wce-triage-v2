#!/usr/bin/python3

import os, sys, subprocess
env = os.environ.copy()

if __name__ == "__main__":

  for srcdir in [ 'usr/local/lib/python3.6/dist-packages/', 'usr/local/share/wce/triage/', 'usr/local/share/wce/wce-triage-ui/' ]:
    srcpath = os.path.join('/', srcdir)
    for dstdir in [ '/var/lib/netclient/wcetriage_amd64', '/var/lib/netclient/wcetriage_x32' ]:
      dstpath = os.path.join(dstdir, srcdir)
      cmd = "sudo rsync -av --delete {src} {dst}".format(src=srcpath, dst=dstpath)
      print(cmd)
      subprocess.run(cmd, shell=True)
      pass
    pass
  pass
