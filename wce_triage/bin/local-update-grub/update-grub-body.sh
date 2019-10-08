#!/bin/sh
#
# Actual running of update-grub - the easy part
#

mount -t proc none /proc
mount -t sysfs none /sys
mount -t devpts none /dev/pts
#
export GRUB_DISABLE_OS_PROBER=true

# Set up the grub.cfg
update-grub

# clean up
umount /proc || umount -lf /proc
umount /sys
umount /dev/pts


