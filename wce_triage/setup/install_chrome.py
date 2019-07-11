#!/usr/bin/python3
#
import os, sys, subprocess

if __name__ == "__main__":
  #
  #
  # Add Google signing key
  #
  subprocess.run('wget -qO- https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo -H apt-key add -', shell=True)
  
  # Using add-apt-repository using google's source list result in error as it exports both i386 and amd64 but 18.04 doesn't support i386 and complains.
  #
  google_chrome_list = open('/tmp/google-chrome.list', 'w')
  google_chrome_list.write('deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main\n')
  google_chrome_list.close()
  subprocess.run("sudo -H install -m 0444 /tmp/google-chrome.list /etc/apt/sources.list.d/google-chrome.list", shell=True)
  
  #
  subprocess.run('sudo -H apt update', shell=True)
  #
  # Install Google Chrome
  #
  subprocess.run('sudo -H apt install -y --no-install-recommends google-chrome-stable', shell=True)
  pass

