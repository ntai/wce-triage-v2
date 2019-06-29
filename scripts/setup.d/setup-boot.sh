#!/bin/sh

cat > /tmp/grub.cfg <<EOF
GRUB_DEFAULT=0
GRUB_TIMEOUT=10
GRUB_DISTRIBUTOR=
GRUB_CMDLINE_LINUX_DEFAULT="aufs=tmpfs"
GRUB_CMDLINE_LINUX=""
GRUB_BACKGROUND="/usr/local/share/wce/triage/assets/wceboot2.png"
EOF

sudo install /tmp/grub.cfg /etc/default/grub
#
sudo update-grub
#
sudo update-initramfs -u
