#!/usr/bin/python3
#
# Install Ubunto packages (some are python packages)
#
import os, subprocess, re, tempfile

from ..const import const

def install_vscode():
  """Install Visual Studio Code. 
  2020-12-06: updated based on https://code.visualstudio.com/docs/setup/linux
  """
  subprocess.run('curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg', shell=True)
  subprocess.run('sudo -H install -o root -g root -m 644 packages.microsoft.gpg /usr/share/keyrings/', shell=True)
  subprocess.run('sudo -H install -o root -g root -m 644 packages.microsoft.gpg /etc/apt/trusted.gpg.d/', shell=True)

  cat = subprocess.Popen('sudo -H tee /etc/apt/sources.list.d/vscode.list', shell=True, stdin=subprocess.PIPE)
  cat.communicate("deb [arch=amd64 signed-by=/etc/apt/trusted.gpg.d/packages.microsoft.gpg] https://packages.microsoft.com/repos/vscode stable main".encode('iso-8859-1'))
  subprocess.run('sudo -H apt-get update', shell=True)
  subprocess.run('sudo -H apt-get install code', shell=True) # or code-insiders
  pass

#
if __name__ == "__main__":
  install_vscode()
  pass
