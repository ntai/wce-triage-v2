# TODO

Here is the things need to be solved.

## Backend

 - Make bootable disk
   - For MBR boot, use grub (DONE)
     I have done this in version 1, so I should know the ingredients
     but (a) it's a long time ago, and I have to remember. (b) many
     many things have been changed so much that I probably need to
     make sure the oldies-but-goodies still works.
     - Create partitions
     - Restore data partition
     - Install GRUB
     - Bless
     
   - For EFI boot, manipulate EFI
     Most likely, I should push this to the future because
     90% of computers are still using MBR boot, and 100% of
     computers are MBR bootable.
     - Creating partition using parted - done
     - Creating EFI parition - unknown

 - Create disk image
   Instead of hardcoding the destination, since there is a UI,
   choose desination possible.
   Disable auto-mount of usb media
   - systemctl mask udisks2

 - Restore disk image

 - Websocket based reporer for frontend

 - http server
   This is kind of working.
   - serving static file - done
   - serving restore disk
   - serving create disk image
   
## Frontend
 need to learn a bit more about React.js
 
 - Triage UI - in-progress
   Using react.js is probably super overkill

 - Loading disk image
   - Make the progress rows using individual state in table so the
     state can be updated through websocket.


## current task

Installing for i386-pc platform.
/usr/sbin/grub-install: warning: this GPT partition label contains no BIOS Boot Partition; embedding won't be possible.
/usr/sbin/grub-install: warning: Embedding is not possible.  GRUB can only be installed in this setup by using blocklists.  However, blocklists are UNRELIABLE and their use is discouraged..
/usr/sbin/grub-install: error: will not proceed with blocklists.
Sourcing file `/etc/default/grub'
Generating grub configuration file ...
Found linux image: /boot/vmlinuz-4.15.0-51-generic
Found initrd image: /boot/initrd.img-4.15.0-51-generic
Found Ubuntu 18.04.2 LTS (18.04) on /dev/sda1
Found Windows Recovery Environment on /dev/sdb2
Found Windows 8 on /dev/sdb4
done
