#!/usr/bin/python3
#
# This is for Triage USB stick on mini system
#
import os, sys, subprocess

grub_cfg = open('/tmp/grub.cfg', 'w')
grub_cfg.write('''GRUB_DEFAULT=0
GRUB_TIMEOUT=10
GRUB_DISTRIBUTOR=
GRUB_CMDLINE_LINUX_DEFAULT="aufs=tmpfs"
GRUB_CMDLINE_LINUX=""
GRUB_BACKGROUND="/usr/local/share/wce/triage/assets/wceboot2.png"
''')
grub_cfg.close()

subprocess.run(['sudo', 'install', '/tmp/grub.cfg', '/etc/default/grub'])
#
subprocess.run(['sudo', 'update-grub'])
#
subprocess.run(['sudo', 'update-initramfs', '-u'])
               
