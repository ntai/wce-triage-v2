#!/usr/bin/python3
#
# Install Ubunto packages (some are python packages)
#
import os
import subprocess


if __name__ == "__main__":
  if os.environ.get('WCE_TRIAGE_DISK') == "true":
    # I'm a bit tired of figuring this out for the minimal server. 
    # This adds about 40Mb but so be it
    subprocess.run('sudo -H apt install gstreamer1.0-x', shell=True)
    pass
  pass
