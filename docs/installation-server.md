# Setting up a network server for client netboot

Overview

1. Install the latest Ubuntu server
2. Install Python-3 pip
3. Install wce_triage Python package
4. Run the set up script
5. Set up the ethernet ports
4. Copy WCE triage disk to the server
5. Create the triage disk overay for the NFS root
6. Set up the PXE boot files
4. Set up NFS, TFTP, HTTP and dnsmasq

## Download and install the Ubuntu server
Do not use single partition. Create the payload and swap partitions. Root partition is 32GB. (can be smaller?)
Choose "minimul" - VERY important to keep the footprint small.

* / (32GB)
* swap (4GB)
* /payload (Rest)

Use `wceserve` for hostname, use `wce` as the login name.

Base system takes up 4GB, and the installer creates 8GB `/swap.img` file. After the initial installation, `sudo rm /swap.img`.

To do so, you need to edit `/etc/fstab` to remove the entry.


## Install pip3

```
sudo -H apt install -y python3-pip --no-install-recommends
sudo apt install emacs # not optional (LOL)

```

Yes, you do not need to install Emacs.

## Install wce_triage
wce_triage package is on test.pypi.org.

```
sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage
```

## Run the set up script

```
sudo python3 -m wce_triage.setup.setup_network_server
```
If this is 22.04, you'd need 0.5.1.

This should install all of the packages, etc.

## Set up the ethernet ports

Use netplan, as there is no UI (probably), and better. It should look like this. 

```
network:
  version: 2
  renderer: networkd
  ethernets:
    enp4s0:
      dhcp4: yes
      optional: yes
    enp2s0:
      dhcp4: no
      optional: yes
    enp3s0:
      dhcp4: no
      optional: yes
  bonds:
      bond0:
        interfaces: [enp2s0, enp3s0]
        addresses: [ 10.3.2.1/24 ]
```

`python3 -m wce_triage.lib.netplan` prints the cheat sheet.

## Copy WCE triage disk to the server

```
sudo mkdir /disk1 && mount /dev/sd?2 /disk1
sudo mkdir -p /payload/wce/triage/installer/amd64
sudo rsync -av /disk1/ /payload/wce/triage/installer/amd64/
```

## Setting up client NFS root 

Once the triage disk is copied, it needs to change `/etc/fstab` so that netboot finds the NFS root dir.
In the past, this is done patching the file. Lately, this is done by aufs up to 20.04. 22.04 favors overayfs, and aufs-tools is not available.

```
# <file system> <mount point>   <type>  <options>       <dump>  <pass>
/dev/disk/by-uuid/d7a28055-0ede-4e61-a052-8bb913f8cef1 none swap sw 0 0
# / was on /dev/sda2 during curtin installation
/dev/disk/by-uuid/e66fb071-708e-42f3-b050-c1bb569ccdd8 / ext4 defaults 0 1
# /payload was on /dev/sda4 during curtin installation
/dev/disk/by-uuid/cfad0137-1187-4931-a567-38e701862aa0 /payload ext4 defaults 0 1
# /boot/efi was on /dev/sda1 during curtin installation
/dev/disk/by-uuid/1989-D224 /boot/efi vfat defaults 0 1

overlay /var/lib/netclient/wcetriage_amd64  overlay x-systemd.requires=/payload,workdir=/payload/wce/triage/amd64-workdir,upperdir=/payload/wce/triage/installer/amd64-overlay,lowerdir=/payload/wce/triage/installer/amd64,nfs_export=on 0 2
/payload/wce/wce-disk-images x-systemd.requires=/payload,/usr/local/share/wce/wce-disk-images none x-systemd.requires=/payload,bind 0 2
```

## pxeboot by dnsmasq and tftp

This should have been set up by the setup script.
However, the kernel and init file come from the triage disk.

1. PXE gets an client IP and tftp host (10.3.2.1)
2. PXE entry provides kernel and initrd file names
3. Client gets kernel/initrd from tftp 

In 22.04, the setup script does not kill off the default name resolver.

```
sudo systemctl enable dnsmasq 
sudo systemctl start dnsmasq 
```

Make sure dnsmasq excludes the non-bond-ed networks from DHCP.
Since the network interface is machine dependant, you need to update `/etc/dnsmasq.conf` accordingly.
Note that, `port=0` stops the DNS of dnsmasq. Keep the resolved. 
Maybe setting the server to localhost is better.


```
no-dhcp-interface=enp4s0
no-hosts
expand-hosts
no-resolv
port=0
address=/wceserve/10.3.2.1
dhcp-range=10.3.2.100,10.3.2.199,2h
dhcp-option=3,10.3.2.1
dhcp-option=6,10.3.2.1
pxe-service=x86PC, "Boot from local disk"
pxe-service=x86PC, "WCE Triage/Ubuntu", pxelinux
```


## /var/lib/netboot/wce_amd64

```
cd /var/lib/netboot/wce_amd64
cp ../../netclient/wcetriage_amd64/boot/vmlinuz ./
cp ../../netclient/wcetriage_amd64/boot/initrd.img ./
chmod 644 *
```
With permission, etc. come in to play, don't be cute and use symlink here. Just copy those two and be done with it.

NOTE: Be sure to chmod. TFTP is not root and had a few head scratching happened before.

## Disable cloud service
22.04 added this and badly interfares with startup.

```
sudo touch /etc/cloud/cloud-init.disabled
```
