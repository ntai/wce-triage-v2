#!/usr/bin/python3
#
# Install Ubunto packages (some are python packages)
#
import os, sys, subprocess

# python3-aiohttp python3-aiohttp-cors - triage backend.
# yes, you can cross-domain
# probably, not used for live triage.

triage_packages = [
  'python3-pip',              # bootstrapping pip3 ???
  'gnupg',                    # for Google key installation
  'dmidecode',                # decoding bios, detects memory
  'efibootmgr',               # for EFI boot (not yet implemented, sadly)
  'gdisk',                    # gdisk
  'grub2-common',             # boot manager
  'grub-pc',                  # boot manager
  'mg',                       # small emacs-like editor
  'pigz',                     # parallel gzip
  'partclone',                # partclone
  'parted',                   # parted
  'alsa-utils',               # Audio
  'pulseaudio',               # Ubuntu audio server
  'pulseaudio-utils',         # Ubuntu PA utils
  'python3-aiohttp',          # for python http server
  'python3-aiohttp-cors',     # for python http server
  'python3-psutil'            # Socket IO to work with aiohttp
]

# aufs-tools - for making usb stick to boot and mount memory file system as read/write over read-only usb storage
#
# xserver-xorg-legacy - Ubuntu 18.04LTS needs to run X11 server as root. Setting video mode requires the root priv.
#   This may change in future. Also, this pops up a dialog. If you see it, choose "everyone".
#
# vbetool - video buffer tool
# gfxboot - pretty boot screen
# lighttpd - serving payload. much better than using python.

kiosk_packages = [
  'xorg',
  'openbox',
  'aufs-tools',
  'xserver-xorg-video-all',
  'xserver-xorg-video-vmware',
  'vbetool',
  'gfxboot',
  'lighttpd'
]

# python-socketio - websocket.
# I would have used the ubuntu package if provided.
# semms to not work for now.
#
python_packages = ['python-socketio']

#
#
#
server_packages = [
  'atftpd',
  'lighttpd',
  'dnsmasq',
  'nfs-common',
  'nfs-kernel-server',
  'openssh-server'
]

if __name__ == "__main__":
  packages = triage_packages

  if os.environ.get('WCE_TRIAGE_DISK') == "true":
    subprocess.run('sudo -H apt remove -y apparmor', shell=True)
    packages = packages + kiosk_packages
    pass

  if os.environ.get('WCE_SERVER') == "true":
    packages = packages + server_packages
    pass

  installed_packages = {}

  apt_list = subprocess.run(['apt', 'list', '--installed'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  for pkg_line in apt_list.stdout.decode('iso-8859-1').splitlines():
    pkg_line = pkg_line.strip()
    if '/' in pkg_line:
      installed_packages[pkg_line.split('/')[0]] = pkg_line
      pass
    pass

  
  for package in packages:
    if installed_packages.get(package):
      continue
    subprocess.run(['sudo', '-H', 'apt', 'install', '-y', '--no-install-recommends', package])
    pass

  # install python packages.
  #  Why not use pip3? Ubuntu server is far more stable than pypi server.
  #  Also, the packages on pypi moves too fast and dependencies can be a headache.
  #
  for ppkg in python_packages:
    subprocess.run(['sudo', '-H', 'pip3', 'install', ppkg])
    pass
  pass
