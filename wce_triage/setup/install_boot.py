#!/usr/bin/python3
#
# 
import os, sys, subprocess

if os.getuid() != 0:
    print("***** install_boot would only work as root *****")
    sys.exit(1)
#
subprocess.run(['update-grub'])
#
subprocess.run(['update-initramfs', '-u'])

#
subprocess.run(['mkdir', '/ro'])
subprocess.run(['mkdir', '/rw'])

