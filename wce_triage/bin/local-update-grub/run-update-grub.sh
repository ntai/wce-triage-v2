#!/bin/sh
DISK=$1
MOUNTPOINT=/mnt/$DISK

FULLPATH=$(realpath $0)
MYDIR=$(dirname $FULLPATH)

set -x

#
sudo -H mkdir -p $MOUNTPOINT
sudo -H mount $DISK $MOUNTPOINT

sudo -H cp $MYDIR/update-grub-body.sh $MOUNTPOINT/update-grub-body.sh

# Set up the /dev for chroot
sudo -H mount --bind /dev/ $MOUNTPOINT/dev
sudo -H /usr/sbin/chroot $MOUNTPOINT /bin/sh /update-grub-body.sh

sudo -H rm $MOUNTPOINT/update-grub-body.sh
#sudo -H umount $DISK
