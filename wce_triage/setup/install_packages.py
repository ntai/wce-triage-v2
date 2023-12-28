#!/usr/bin/python3
#
# Install Ubunto packages (some are python packages)
#
import os
import subprocess
import tempfile

from ..const import const
from .install_vscode import install_vscode
from . import get_ubuntu_release

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


ppa_list = {
  '22.04': [
    'ppa:ubuntu-mozilla-security/ppa',
  ],
  '24.04': [
    'ppa:ubuntu-mozilla-security/ppa',
  ]
}

# python3-aiohttp python3-aiohttp-cors - triage backend.
# yes, you can cross-domain
# probably, not used for live triage.


base_packages = {
  None: [
    'python3-pip',              # bootstrapping pip3 ???
    'alsa-utils',               # Audio
    'curl',                     # cURL
    'gnupg',                    # for Google key installation
    'dmidecode',                # decoding bios, detects memory
    'efibootmgr',               # for EFI boot (not yet implemented, sadly)
    'gdisk',                    # gdisk
    'grub2-common',             # boot manager
    'grub-pc',                  # boot manager
    'hardinfo',                 # hardinfo - hardware profiling app
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
    'fonts-roboto',             # Google's fonts for UI.
    'wpasupplicant',            # wifi auth
    #
    # Network device Firmware
    #
    'linux-firmware',
    'firmware-b43-installer',
    'firmware-b43legacy-installer',
    'firmware-ath9k-htc',
    'linux-wlan-ng-firmware',   # wlan fw
    'prism2-usb-firmware',

    # audio device firmware
    'alsa-firmware-loaders',

    #
    'parallel',
    #
    # Network
    #
  ],
  '18.04': [
    'iwconfig',                 # for seeing wifi device list
  ],
  '20.04': [
    'iw',                       # for seeing wifi device list
    'nmcli',                    # connect to wifi through nmcli command
    'firefox',                  # Use firefox
    'xdg-utils',
    'build-essential',
    'overlayroot',
  ],
  '22.04': [
    'iw',                       # for seeing wifi device list
    'nmcli',                    # connect to wifi through nmcli command
    'xdg-utils',
    'build-essential',
    'overlayroot',
  ],
  '24.04': [
    'iw',                       # for seeing wifi device list
    'nmcli',                    # connect to wifi through nmcli command
    'xdg-utils',
    'build-essential',
    'overlayroot',
  ],
}


#
# xserver packages - this is in the base package but it's easier to see
#
xorg_packages = {
  None: [
    'xorg',
    'xserver-xorg-video-all',
    'xserver-xorg-video-fbdev',
    'xserver-xorg-video-intel',
    'xserver-xorg-video-vmware',
    'xserver-xorg-video-openchrome',
    'xserver-xorg-video-vesa',
    'xbacklight'
  ],
  '18.04': [
    'xserver-xorg-video-geode',
    'xserver-xorg-video-mach64',
    'xserver-xorg-video-r128',
    'xserver-xorg-video-savege',
    'xserver-xorg-video-trident',
  ],
  '20.04': [
    'xserver-xorg-video-mga',
  ],
  '22.04': [
    'xserver-xorg-video-mga',
  ],
  '24.04': [
    'xserver-xorg-video-mga',
  ]
}


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

for_server_minimal = [
    # Because the minimal server contains very little, this list is longer.
    # Maybe not using the minimal makes things easier but then it may include
    # man pages
    'pulseaudio-utils',
    'iproute2',
    'overlayroot',
    'build-essential',          # Needed to build python packages. Should be uninstalled at the end
    'python3-dev'
    'gcc',
    'fdisk',
    'isc-dhcp-client',          # needs to be marked install
    'netplan.io',
    'python3-requests',
    'python3-urllib3',
]

triage_kiosk_packages = {
  None: [
    'openbox',
    'vbetool',
    'gfxboot',
    'lighttpd',
    'hardinfo',
    'smartmontools'
  ],
  '18.04': [],
  '20.04': [
    'overlayroot',
    'build-essential',
    'gcc',
  ],
  '22.04': for_server_minimal + [
  ],
  '24.04': for_server_minimal + [
  ],
}

# For existing triage server, these packages are needed.
# 

wce_triage_python_packages = {
  None: [
    "aiohttp==3.6.2",
    "aiohttp-cors==0.7.0",
    "python-socketio==5.6.0"
  ]
}

# Some interesting packages.
desktop_python_packages = {
  None: [
    'tensorflow==2.0.0b1',
    'numpy==1.16.*',
    'tensorflow-datasets',
    'h5py'
  ]
}

#
# Packages for the server
#
server_packages = {
  None: [
    'tftpd',
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
    'python3-distutils',
    'beep',
    'syslog-ng',
  ],
  '18.04': [],
  '20.04': [],
  '22.04': [],
  '24.04': [],
}


#
# Packages for desktop client
#
desktop_packages = {
  None: [
    'arduino',
    'audacity',
    'seahorse',
    'eclipse',
    'gpg',
    'apt-transport-https',
    'octave',
    'octave-doc',
    'gperiodic',
    'gdis',
    'chemical-structures',
    'chemtool',
    'easychem',
    'cp2k',
    'cp2k-data',
    'zlib1g',
    'etoys',
    'etoys-doc',
    'libicu60',
    'libpugixml1v5',
    'liblzma5',
    'libxapian30',
    'libcurl4',
    'libmicrohttpd12',
    'zlib1g',
    'libicu60',
    'libpugixml1v5',
    'liblzma5',
    'libxapian30',
    'libcurl4',
    'libmicrohttpd12',
    # GNU Octave and friends
    'gnuplot-qt',
    'gnuplot-x11',
    'g++',
    'gcc',
    'libopenblas-base',
    'libatlas3-base'
    'pstoedit',
    'epstool',
    'default-jre-headless',
  ],
  '18.04': [
    'ubuntu-edu-preschool',
    'ubuntu-edu-primary',
    'ubuntu-edu-secondary',
    'ubuntu-edu-tertiary',
  ],
  '20.04': [
    
  ],
  '22.04': [
  ],
  '24.04': [],
}

external_packages = {
  None: [],
  '18.04': [],
  '20.04' : [
    ( './preschool.deb', ['curl', '-L', '-o', 'preschool.deb', 'https://drive.google.com/uc?export=download&id=1xYANzX2gZMKzurZ-qC7hPQjLUkrEsaBy'] ),
    ( './primary.deb',   ['curl', '-L', '-o', 'primary.deb',   'https://drive.google.com/uc?export=download&id=1JNn5EvNPnR2XyWJVImVDa2qAQXLhOab7'] ),
    ( './secondary.deb', ['curl', '-L', '-o', 'secondary.deb', 'https://drive.google.com/uc?export=download&id=1kuuSriqjDGBa9XgOctV4a5FkUOQ80A8Y'] ),
    ( './tertiary.deb',  ['curl', '-L', '-o', 'tertiary.deb',  'https://drive.google.com/uc?export=download&id=1b_vbnKZcLBMfGbkSfrUkvPUin7U2LKAm'] ),
  ],
  '22.04': [
    ('./preschool.deb', ['curl', '-L', '-o', 'preschool.deb',
                         'https://drive.google.com/uc?export=download&id=1xYANzX2gZMKzurZ-qC7hPQjLUkrEsaBy']),
    ('./primary.deb', ['curl', '-L', '-o', 'primary.deb',
                       'https://drive.google.com/uc?export=download&id=1JNn5EvNPnR2XyWJVImVDa2qAQXLhOab7']),
    ('./secondary.deb', ['curl', '-L', '-o', 'secondary.deb',
                         'https://drive.google.com/uc?export=download&id=1kuuSriqjDGBa9XgOctV4a5FkUOQ80A8Y']),
    ('./tertiary.deb', ['curl', '-L', '-o', 'tertiary.deb',
                        'https://drive.google.com/uc?export=download&id=1b_vbnKZcLBMfGbkSfrUkvPUin7U2LKAm']),
  ]

}
  

def get_ppa_list(ppa_list, release_version) -> list:
  return ppa_list.get(None, []) + ppa_list.get(release_version, [])


def get_package_list(package_list, release_version) -> list:
  return package_list.get(None, []) + package_list.get(release_version, [])


def get_package_plan(release_version):
  packages = get_package_list(base_packages, release_version) + get_package_list(xorg_packages, release_version)

  if os.environ.get('WCE_TRIAGE_DISK') == "true":
    subprocess.run('sudo -H apt remove -y apparmor', shell=True)
    packages = packages + get_package_list(triage_kiosk_packages, release_version)
    pass

  if os.environ.get(const.WCE_SERVER) == "true":
    packages = packages + get_package_list(server_packages, release_version)
    pass

  if os.environ.get('WCE_DESKTOP') == "true":
    packages = packages + get_package_list(desktop_packages, release_version)
    pass
  return packages


if __name__ == "__main__":
  sudo = 'sudo'

  release_version = get_ubuntu_release()

  ppas = get_ppa_list(ppa_list, release_version)
  if ppas:
    for ppa in ppas:
      subprocess.run([sudo, '-E', '-H', "add-apt-repository", "-n", "-y", ppa])
      pass
    subprocess.run([sudo, '-E', '-H', "apt", "update"])
    pass

  packages = get_package_plan(release_version)
  installed_packages = list_installed_packages()

  for package in packages:
    if installed_packages.get(package):
      continue
    subprocess.run([sudo, '-E', '-H', 'apt', 'install', '-y', '--no-install-recommends', package])
    pass

  if os.environ.get('WCE_DESKTOP') == "true":
    install_vscode()

    # install external packages
    # Edubuntu is now released as separate meta packages in google drive.
    # 
    cwd = os.getcwd()
    tempdir = tempfile.mkdtemp()
    os.chdir(tempdir)
    ext_package_files = []
    for deb_name, pkg_argv in get_package_list(external_packages, release_version):
      ext_package_files.append(deb_name)
      subprocess.run(pkg_argv)
      subprocess.run([sudo, 'apt', 'install', '--fix-broken', '-y', '--no-install-recommends', deb_name])
      pass
    os.chdir(cwd)
    pass

  # install python packages.
  #  Why not use pip3? Ubuntu server is far more stable than pypi server.
  #  Also, the packages on pypi moves too fast and dependencies can be a headache.

  python_packages = get_package_list(wce_triage_python_packages, release_version)
  if os.environ.get('WCE_DESKTOP') == "true":
    python_packages = python_packages + get_package_list(desktop_python_packages, release_version)
    pass
  
  for ppkg in python_packages:
    subprocess.run([sudo, '-E', '-H', 'pip3', 'install', ppkg])
    pass
  pass
