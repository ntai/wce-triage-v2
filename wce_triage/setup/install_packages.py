#!/usr/bin/python3
#
# Install Ubunto packages (some are python packages)
#
import os, sys, subprocess
from ..const import *

# python3-aiohttp python3-aiohttp-cors - triage backend.
# yes, you can cross-domain
# probably, not used for live triage.

base_packages = [
  'python3-pip',              # bootstrapping pip3 ???
  'alsa-utils',               # Audio
  'gnupg',                    # for Google key installation
  'dmidecode',                # decoding bios, detects memory
  'efibootmgr',               # for EFI boot (not yet implemented, sadly)
  'gdisk',                    # gdisk
  'grub2-common',             # boot manager
  'grub-pc',                  # boot manager
  'iwconfig',                 # for seeing wifi device list
  'make',                     # make makes 
  'mg',                       # small emacs-like editor
  'net-tools',                # netstat
  'nfs-common',               # mounting nfs
  'nvme-cli',                 # nvme cli commands
  'pigz',                     # parallel gzip
  'patch',                    # patch - needed to patch config files
  'partclone',                # partclone
  'parted',                   # parted
  'pulseaudio',               # Ubuntu audio server
  'pulseaudio-utils',         # Ubuntu PA utils
  'python3-aiohttp',          # for python http server
  'python3-aiohttp-cors',     # for python http server
  'rfkill',                   # rfkill reports the wifi hardware/software switches
  'wpasupplicant',            # wifi auth
  #
  # Network device Firmware
  #
  'linux-firmware',
  'firmware-b43-installer',
  'firmware-b43legacy-installer',
  'firmware-ath9k-htc',
  'linux-wlan-ng-firmware',   # wlan fw

  # audio device firmware
  'alsa-firmware-loaders',
]

#
# xserver packages - this is in the base package but it's easier to see
#
xorg_packages = [
  'xorg',
  'xserver-xorg-video-all',
  'xserver-xorg-video-fbdev',
  'xserver-xorg-video-intel',
  'xserver-xorg-video-vmware',
  'xserver-xorg-video-geode',
  'xserver-xorg-video-mach64',
  'xserver-xorg-video-openchrome',
  'xserver-xorg-video-r128',
  'xserver-xorg-video-savege',
  'xserver-xorg-video-trident',
  'xserver-xorg-video-vesa',
  'xbacklight'
  ]

#
# Triage system packages
#
# aufs-tools - for making usb stick to boot and mount memory file system as read/write over read-only usb storage
#
#
# vbetool - video buffer tool
# gfxboot - pretty boot screen
# lighttpd - serving payload. much better than using python.
#
# Note that the browser is installed by install_chrome.py
#
triage_kiosk_packages = [
  'openbox',
  'aufs-tools',
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
  'emacs',
  'openbsd-inetd',
  'nfs-common',
  'nfs-kernel-server',
  'openssh-server',
  'pxelinux',
  'syslinux',
  'syslinux-common',
  'python3-distutils'
]

if __name__ == "__main__":
  packages = base_packages + xorg_packages

  if os.environ.get('WCE_TRIAGE_DISK') == "true":
    subprocess.run('sudo -H apt remove -y apparmor', shell=True)
    packages = packages + triage_kiosk_packages
    pass

  if os.environ.get(const.WCE_SERVER) == "true":
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
