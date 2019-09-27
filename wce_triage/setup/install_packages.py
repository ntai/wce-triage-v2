#!/usr/bin/python3
#
# Install Ubunto packages (some are python packages)
#
import os, sys, subprocess

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
  'pigz',                     # parallel gzip
  'patch',                    # patch - needed to patch config files
  'partclone',                # partclone
  'parted',                   # parted
  'pulseaudio',               # Ubuntu audio server
  'pulseaudio-utils',         # Ubuntu PA utils
  'python3-aiohttp',          # for python http server
  'python3-aiohttp-cors',     # for python http server
  'rfkill',                   # rfkill reports the wifi hardware/software switches
  'wpasupplicant'
]

#
# xserver packages - this is in the base package but it's easier to see
#
xorg_packages = [
  'xorg',
  'xserver-xorg-video-all',
  'xserver-xorg-video-vmware',
  'xserver-xorg-video-geode',
  'xserver-xorg-video-r120',
  'xserver-xorg-video-mach64',
  ]

#
# Triage system packages
#
triage_packages = [
  'network-manager'          # Install full network manager
]


# aufs-tools - for making usb stick to boot and mount memory file system as read/write over read-only usb storage
#
#
# vbetool - video buffer tool
# gfxboot - pretty boot screen
# lighttpd - serving payload. much better than using python.

kiosk_packages = [
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
    packages = packages + kiosk_packages + triage_packages
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
