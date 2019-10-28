#!/usr/bin/python3

import os, sys, subprocess

if __name__ == "__main__":
  os.chdir('/usr/local/share/wce/wce-triage-ui')
  subprocess.run('sudo -H rm -fr /usr/local/share/wce/wce-triage-ui/*', shell=True)
  subprocess.run('cd /usr/local/share/wce/wce-triage-ui && sudo -H curl -L -o - "https://drive.google.com/uc?export=download&id=1eNzcClc_rLebtwhR2KDfZbMA9c9W_P2Y" | tar xzf -', shell=True)
  pass
