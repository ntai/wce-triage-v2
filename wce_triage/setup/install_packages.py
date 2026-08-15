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


# ppa:ubuntu-mozilla-security/ppa used to live here. It has nothing newer than
# jammy and only ever published cargo, so on 24.04/26.04 it produced
# "does not have a Release file" and broke every following apt update.
# Non-snap Firefox comes from ppa:mozillateam/ppa in install_firefox.py.
ppa_list = {
}

# The triage backend is fastapi + uvicorn out of a venv (see pyproject.toml).
# It needs no python packages from apt.


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
    # NO 'pulseaudio' here. From 23.04 on, the audio server is PipeWire, and
    # pipewire-audio declares Conflicts: pulseaudio. Installing pulseaudio on
    # 24.04/26.04 drags out pipewire-audio and every desktop metapackage that
    # depends on it - on 26.04 budgie it removed ubuntu-budgie-desktop and
    # ubuntu-budgie-desktop-minimal. Per-release audio server is below.
    # 'pulseaudio-utils',         # pactl/paplay - talk to PipeWire's pulse shim too
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

    # audio device firmware
    'alsa-firmware-loaders',

    #
    # Bluetooth stack + firmware
    #
    'bluez',                    # Bluetooth daemon/tools - core BT stack
    'bluez-firmware',           # firmware for Broadcom/misc BT adapters not in linux-firmware

    #
    'parallel',
    #
    # Network
    #
  ],
  '18.04': [
    'iwconfig',                 # for seeing wifi device list
    'prism2-usb-firmware',
    'linux-wlan-ng-firmware',   # wlan fw
  ],
  '20.04': [
    'iw',                       # for seeing wifi device list
    'nmcli',                    # connect to wifi through nmcli command
    'firefox',                  # Use firefox
    'xdg-utils',
    'build-essential',
    'overlayroot',
    'ubuntu-restricted-extras',
    'prism2-usb-firmware',
    'linux-wlan-ng-firmware',   # wlan fw
  ],
  '22.04': [
    'iw',                       # for seeing wifi device list
    'network-manager',          # connect to wifi through nmcli command
    'xdg-utils',
    'build-essential',
    'overlayroot',
    'firmware-sof-signed',
    'ubuntu-restricted-extras',
    'prism2-usb-firmware-installer',
    'linux-wlan-ng',
    'linux-wlan-ng-firmware',   # wlan fw
  ],
  '24.04': [
    'iw',                       # for seeing wifi device list
    'network-manager',          # connect to wifi through nmcli command
    'xdg-utils',
    'build-essential',
    'overlayroot',
    'ubuntu-restricted-extras',
    'pipewire-audio',           # audio server. Replaced pulseaudio in 23.04.
    'firmware-realtek-rtl8723cs-bt',
    'r8125-dkms',
    'r8168-dkms',
    'rtl8812au-dkms',
    'broadcom-sta-dkms',
  ],
  '26.04': [
    'iw',                       # for seeing wifi device list
    'network-manager',          # connect to wifi through nmcli command
    'xdg-utils',
    'build-essential',
    'overlayroot',
    'ubuntu-restricted-extras',
    'pipewire-audio',           # audio server. Replaced pulseaudio in 23.04.
    'r8125-dkms',
    'r8168-dkms',
    'broadcom-sta-dkms',
    'firmware-carl9170',
    'urfkill',
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
  ],
  '26.04': [
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
    # 'pulseaudio-utils',
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
    'hardinfo',
    'smartmontools'
  ],
  '18.04': [
    'lighttpd',
  ],
  '20.04': [
    'overlayroot',
    'build-essential',
    'gcc',
    'lighttpd',
  ],
  '22.04': for_server_minimal + [
    'lighttpd',
  ],
  '24.04': for_server_minimal + [
    'lighttpd',
  ],
  '26.04': for_server_minimal + [
    'nginx',
  ],
}

# The triage server's own python dependencies are not installed from here.
# It is fastapi + uvicorn running out of a venv - pyproject.toml owns that list.

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
  '18.04': [
    'lighttpd',
  ],
  '20.04': [
    'lighttpd',
  ],
  '22.04': [
    'lighttpd',
  ],
  '24.04': [
    'lighttpd',
  ],
  '26.04': [
    "nginx"
  ],
}


#
# Packages for desktop client
#
desktop_packages = {
  None: [
    'arduino',
    'audacity',
    'seahorse',
    'gpg',
    'apt-transport-https',
    # Kiwix - offline wikipedia. kiwix-tools provides kiwix-serve.
    'kiwix-tools',
    'zlib1g',
    'liblzma5',
    'libpugixml1v5',
    'libxapian30',
    # GNU Octave and friends
    'octave',
    'octave-doc',
    # gnuplot-qt and gnuplot-x11 both provide gnuplot and conflict, so listing
    # both made every setup run swap one for the other. qt is the desktop one.
    'gnuplot-qt',
    'g++',
    'gcc',
    'libopenblas0',
    'libatlas3-base',
    'pstoedit',
    'epstool',
    'default-jre-headless',
    # Chemistry
    'chemical-structures',
    'chemtool',
    'easychem',
    'cp2k',
    'cp2k-data',
    'avogadro',            # molecule editor/viewer
    'kalzium',             # periodic table (replaces gperiodic)
    # Math
    'maxima',
    'wxmaxima',
    # Astronomy, geography
    'stellarium',
    'kgeography',
    'marble',
    # Physics
    'step',                # interactive physics simulator
    # Python for students
    'python3-numpy',
    'python3-scipy',
    'python3-matplotlib',
    'python3-pandas',
    'python3-sympy',
    'python3-tk',
    'thonny',              # beginner Python IDE
    'idle',
    'jupyter-notebook',
    # Programming
    'git',
    'build-essential',
    'default-jdk',
    'geany',
    'meld',
    'sqlite3',
    # Younger students
    'gcompris-qt',
    'tuxpaint',
    'tuxmath',
    'tuxtype',
    'klavaro',             # touch typing tutor
    'etoys',
    'etoys-doc',
    # Graphics, media
    'gimp',
    'inkscape',
    'krita',
    'dia',                 # diagram editor
    'vlc',
    'ffmpeg',
    # CAD
    'openscad',
    'librecad',
    # Reference, notes
    'zim',                 # desktop wiki / notebook
    'goldendict-ng',       # offline dictionaries, pairs with kiwix
    # Utilities
    'gparted',
    'keepassxc',
  ],
  # Heavy for refurbished hardware. Enable per deployment if the machines can
  # take it: 'blender', 'kdenlive', 'qgis', 'kicad', 'darktable', 'scilab',
  # 'r-base', 'openboard', 'musescore3', 'lmms'
  '24.04': [],
  '26.04': [],
}


# Edubuntu came back as a flavor in 24.04, so ubuntu-edu-* is in universe again
# and the google drive .debs below are no longer needed there.
#
# These metapackages are empty - Installed-Size 12, no Depends, everything in
# Recommends - so they must be installed WITH recommends or they bring nothing.
# That is why they are not in desktop_packages.
recommends_packages = {
  None: [],
  '24.04': [
    'ubuntu-edu-preschool',
    'ubuntu-edu-primary',
    'ubuntu-edu-secondary',
    'ubuntu-edu-tertiary',
  ],
  '26.04': [
    'ubuntu-edu-preschool',
    'ubuntu-edu-primary',
    'ubuntu-edu-secondary',
    'ubuntu-edu-tertiary',
  ],
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
  ],
  '24.04': [],
  '26.04': [],
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
    # Metapackages whose contents are all Recommends. --no-install-recommends
    # would install an empty package and nothing else.
    for package in get_package_list(recommends_packages, release_version):
      if installed_packages.get(package):
        continue
      subprocess.run([sudo, '-E', '-H', 'apt', 'install', '-y', package])
      pass

    install_vscode()

    # install external packages
    # For 20.04 and 22.04, the Edubuntu metapackages were not in the archive and
    # came from google drive. 24.04 brought them back to universe, so those
    # releases use recommends_packages above instead.
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

  # install the extra desktop python packages
  #  Why not use pip3? Ubuntu server is far more stable than pypi server.
  #  Also, the packages on pypi moves too fast and dependencies can be a headache.

  # if os.environ.get('WCE_DESKTOP') == "true":
  #   for ppkg in get_package_list(desktop_python_packages, release_version):
  #     subprocess.run([sudo, '-E', '-H', 'pip3', 'install', ppkg])
  #     pass
  #   pass
  pass
