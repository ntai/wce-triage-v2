#!/usr/bin/python3
#
# Install pxe boot.
#
# as the initrd is copied from the mother system, initrd has to be
# updated and being capable of aufs=tmpfs boot.
#
# FYI: pxelinux is kicked off by /etc/dnsmasq.conf
#
# I realized that, this isn't enough. I need two pieces, one for the templates
# and the UI to drive it. The pxeboot setting probably should come from a config
# file, and natural choice is JSON.
#
import os, sys, distutils.file_util, stat

if os.getuid() != 0:
    print("***** install_boot would only work as root *****")
    sys.exit(1)
#

for ndir in ['/var/lib/netclinet', '/var/lib/netboot', '/var/lib/netboot/pxelinux.cfg', '/var/lib/netboot/wce']:
    if not os.path.exists(ndir):
        os.mkdir(ndir)
        pass
    pass

moduledir = '/usr/lib/syslinux/modules/bios'
destdir = '/var/lib/netboot'

files = ['/usr/lib/PXELINUX/pxelinux.0'] + [ os.path.join(moduledir, module) for module in os.listdir(moduledir) ]

for file in files:
    destfile = os.path.join(destdir, os.path.basename(file))
    distutils.file_util.copy_file(file, destfile, update=True)
    pass

pxelinux_cfg_default = '''DEFAULT vesamenu.c32
TIMEOUT 100
TOTALTIMEOUT 600
PROMPT 0
NOESCAPE 1
ALLOWOPTIONS 1
# MENU BACKGROUND wceboot2.png
MENU MARGEIN 5

MENU TITLE WCE PXE Triage

LABEL WCE Triage 64bit
  MENU DEFAULT
  MENU LABEL WCE ^Triage
  KERNEL wce_amd64/vmlinuz
  APPEND initrd=wce_amd64/initrd.img hostname=bionic nosplash noswap boot=nfs netboot=nfs nfsroot=10.3.2.1:/var/lib/netclient/wcetriage_amd64 acpi_enforce_resources=lax edd=on ip=dhcp aufs=tmpfs ---
  TEXT HELP
  WCE Triage 64bit (amd64)
  ENDTEXT

LABEL WCE Triage 632bit
  MENU LABEL WCE ^32 bit Triage
  KERNEL wce_x32/vmlinuz
  APPEND initrd=wce_x32/initrd.img hostname=bionic nosplash noswap boot=nfs netboot=nfs nfsroot=10.3.2.1:/var/lib/netclient/wcetriage_x32 acpi_enforce_resources=lax edd=on ip=dhcp aufs=tmpfs ---
  TEXT HELP
  WCE Triage 32bit (x86_32)
  ENDTEXT

Label Local
  MENU LABEL Local operating system in harddrive (if available)
  KERNEL chain.c32
  APPEND sda1
  TEXT HELP
  Boot local OS from first hard disk if it's available
  ENDTEXT
'''

pxe_menu = open('/var/lib/netboot/pxelinux.cfg/default', 'w')
pxe_menu.write(pxelinux_cfg_default)
pxe_menu.close()


for src, dest in [ ('/vmlinuz', '/var/lib/netboot/wce/vmlinuz'),
                   ('/initrd.img', '/var/lib/netboot/wce/initrd.img') ]:
    distutils.file_util.copy_file(src, dest, update=True)
    os.chmod(dest, stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH)
    pass
