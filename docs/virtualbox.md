# Workstation setup for VirtualBox

## Before starting

BUG: Using TFTP server - needs the VM name to not include whitespace or underline '_'

## Bootring triage over network
For this, use pxe boot of VirtualBox. It also comes with tftp support.
So, you need NFS but you don't need any of dns/dhcp/pxe/tftp/inetd.

VirtualBox internal NAT addr seems to be hardcoded to 10.0.2.2.


### bootp & tftp

For PXE to work, you need a pxe file in `~/.config/VirtualBox/TFTP/<vm name>.pxe`.
This file should be a symlink.

These come from VirtualBox itself. ~/.config/VirtualBox/TFTP

      cd ~/.config/VirtualBox/TFTP
      ln -s pxelinux.0 <VM NAME>.pxe


### tftp
rsync -av /var/lib/netboot/ ~/.config/VirtualBox/TFTP/


### ~/.config/VirtualBox/TFTP/pxelinux.cfg/default

Note that, in order for this to work, the NFS root mount has to be "rw".

    default vesamenu.c32
    menu resolution 1280 1024
    menu clear
    menu title PXE boot menu
    display boot.msg
    timeout 50
     
    LABEL Local NFS boot
    MENU LABEL Local NFS boot
    KERNEL wce_amd64/vmlinuz
    append initrd=wce_amd64/initrd.img hostname=bionic nosplash noswap boot=nfs vmkopts=debugLogToSerial:1 netboot=nfs nfsroot=10.0.2.2:/var/lib/netclient/wcetriage_amd64 rw acpi_enforce_resources=lax edd=on ip=dhcp wce_share=http://10.0.2.2:8080/wce ---
    
    LABEL Local NFS boot with tmpfs
    MENU LABEL Local NFS boot with tmpfs - read only
    KERNEL wce_amd64/vmlinuz
    append initrd=wce_amd64/initrd.img hostname=bionic nosplash noswap boot=nfs vmkopts=debugLogToSerial:1 netboot=nfs nfsroot=10.0.2.2:/var/lib/netclient/wcetriage_amd64 acpi_enforce_resources=lax edd=on ip=dhcp aufs=tmpfs wce_share=http://10.0.2.2:8080/wce ---

### Configure NFS
Use kernel-nfs-server
You need to export following directories.

    /var/lib/netclient  *(rw,sync,no_wdelay,insecure_locks,no_root_squash,insecure,no_subtree_check)
    /usr/local/share/wce  *(rw,sync,no_wdelay,insecure_locks,no_root_squash,insecure,no_subtree_check)

Once you add these to /etc/exports
     systemctl restart nfs-server

update the fstab for client with the 10.0.2.2
/var/lib/netclient/wcetriage_amd64/etc/fstab

#### /var/lib/netclient

This is where the client's root dir lives. The files are populated from the triage 

     wcetriage_amd64
     wcetriage_x32


##### /var/lib/netclient/wcetriage_amd64/etc/fstab

# <file system> <mount point>   <type>  <options>       <dump>  <pass>
proc            /proc           proc    nodev,noexec,nosuid 0       0
#
# Folloing line is likely gone
#10.3.2.1:/var/lib/netclient/wcetriage.0.1.20  /               nfs   soft,rsize=32768,wsize=32768,proto=tcp,nolock   0       0
#10.3.2.1:/var/lib/netclient/wcetriage.0.1.20  <slash>               nfs   soft,rsize=32768,wsize=32768,proto=tcp,nolock   0       0
#
# rw and ro
#
#none            /rw             tmpfs   defaults        0       0
#10.3.2.1:/var/lib/netclient/wcetriage.0.1.20  /ro             nfs   soft,rsize=32768,wsize=32768,proto=tcp,nolock   0       0
#
none            /tmp            tmpfs   defaults        0       0
none            /var/run        tmpfs   defaults        0       0
none            /var/lock       tmpfs   defaults        0       0
none            /var/tmp        tmpfs   defaults        0       0
#
10.0.2.2:/usr/local/share/wce/wce-disk-images   /usr/local/share/wce/wce-disk-images  nfs   soft,rsize=32768,wsize=32768,proto=tcp,nolock   0       0
#

### Configure lighttpd
This is to find the disk images.
Use port 8080, and 'systemctl restart lighttpd'.
Enable some lightttpd modules, and create a symlink to /usr/local/share/wce

$ python3 ~/sand/wce-triage-v2/wce_triage/setup/configure_lighttpd.py
$ sudo service lighttpd force-reload


