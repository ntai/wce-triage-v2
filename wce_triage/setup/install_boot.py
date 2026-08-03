#!/usr/bin/python3
#
# 
import os, sys, subprocess

from . import get_ubuntu_release

if os.getuid() != 0:
    print("***** install_boot would only work as root *****")
    sys.exit(1)
#
subprocess.run(['update-grub'])
#
subprocess.run(['update-initramfs', '-u'])

# /ro and /rw are mount points for the old aufs-based boot overlay scheme,
# used through 20.04. 22.04+ uses the overlayroot package instead, which
# manages its own overlay mounts - these dirs aren't needed there.
AUFS_RELEASES = ("18.04", "20.04")

if get_ubuntu_release() in AUFS_RELEASES:
    subprocess.run(['mkdir', '/ro'])
    subprocess.run(['mkdir', '/rw'])
    pass

