#!/usr/bin/python3
#
# Cleanup installation
#
import os, subprocess, re, tempfile

from ..const import const
from .install_vscode import install_vscode

def list_installed_packages():
  """Lists and returns installed packages.
  Returns dict, not list.
  """
  installed_packages = {}

  apt_list = subprocess.run(['apt', 'list', '--installed'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  for pkg_line in apt_list.stdout.decode('iso-8859-1').splitlines():
    pkg_line = pkg_line.strip()
    if '/' in pkg_line:
      installed_packages[pkg_line.split('/')[0]] = pkg_line
      pass
    pass
  return installed_packages


base_packages = {
  None: [
  ],
  '18.04': [
  ],
  '20.04': [
  ],
  '22.04': [
  ],
  '24.04': [
  ],
}


#
# xserver packages - this is in the base package but it's easier to see
#
xorg_packages = {
  None: [
  ],
  '18.04': [
  ],
  '20.04': [
  ],
  '22.04': [
  ],
  '24.04': [
  ]
}


#
# Triage system packages
#

triage_packages = {
  None: [
  ],
  '18.04': [],
  '20.04': [],
  '22.04': [
    'build-essential',
    'gcc',
    'cloud-init',
  ],
  '24.04': [
    'build-essential',
    'gcc',
    'cloud-init',
  ]
}

triage_dirs = {
  None: [
  ],
  '18.04': [],
  '20.04': [],
  '22.04': [
    '/etc/cloud',
    '/var/lib/cloud',
  ],
  '24.04': [
    '/etc/cloud',
    '/var/lib/cloud',
  ]
}

# python-socketio - websocket.
# I would have used the ubuntu package if provided.
# semms to not work for now.
#
base_python_packages = {
  None: ['python-socketio']
}


#
# Packages for the server
#
server_packages = {
  None: [],
  '18.04': [],
  '20.04': [],
  '22.04': [],
  '24.04': [],
}


#
# Packages for desktop client
#
desktop_packages = {
  None: [],
  '18.04': [],
  '20.04': [],
  '22.04': [],
  '24.04': [],
}


def get_ubuntu_release():
  release_re = re.compile( 'DISTRIB_RELEASE\s*=\s*(\d+\.\d+)' )
  with open('/etc/lsb-release') as lsb_release_fd:
    for line in lsb_release_fd.readlines():
      result = release_re.search(line)
      if result:
        return result.group(1)
      pass
    pass
  return None


def get_package_list(package_list, release_version) -> list:
  return package_list.get(None, []) + package_list.get(release_version, [])

def get_dir_list(dirs_list, release_version) -> list:
  return dirs_list.get(None, []) + dirs_list.get(release_version, [])


def get_package_purge_plan():
  release_version = get_ubuntu_release()
  packages = get_package_list(base_packages, release_version) + get_package_list(xorg_packages, release_version)

  if os.environ.get('WCE_TRIAGE_DISK') == "true":
    packages = packages + get_package_list(triage_packages, release_version)

    pass

  if os.environ.get(const.WCE_SERVER) == "true":
    packages = packages + get_package_list(server_packages, release_version)
    pass

  if os.environ.get('WCE_DESKTOP') == "true":
    packages = packages + get_package_list(desktop_packages, release_version)
    pass
  return packages, release_version



def get_purge_dirs(release_version):
  dirs = []
  # dirs = get_dir_list(base_dirs, release_version)

  if os.environ.get('WCE_TRIAGE_DISK') == "true":
    dirs = dirs + get_package_list(triage_dirs, release_version)
    pass

  # if os.environ.get(const.WCE_SERVER) == "true":
  #   dirs = dirs + get_package_list(server_dirs, release_version)
  #   pass

  # if os.environ.get('WCE_DESKTOP') == "true":
  #   dirs = dirs + get_package_list(desktop_dirs, release_version)
  #   pass
  return dirs, release_version



if __name__ == "__main__":
  packages, release_version = get_package_purge_plan()
  installed_packages = list_installed_packages()
  
  cmd = 'sudo'

  for package in packages:
    if not installed_packages.get(package):
      continue
    subprocess.run([cmd, '-H', 'apt', 'purge', '-y', package])
    pass

  dirs = get_purge_dirs(release_version)
  for adir in dirs:
      if os.path.exists():
          subprocess.run(['rm', '-rf', adir])
          pass
      pass
          
  pass
