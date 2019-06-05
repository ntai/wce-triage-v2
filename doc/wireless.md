# Broadcom drivers

STA driver does not work with PCI - '14e4:4312'.
This is BCM4311.

Following two modules needs to be removed.

 - bcmwl-kernel-source
 - dkms

To find the PCI ID, do
lspci -vnn | grep -i 14e4:

