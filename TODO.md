# TODO

## Current tasks

 - Improve the UI.
It could be more like wizard style? Especially choosing disk may need to provide more info.

 - CPU rating
Use hardinfo and provide the cpu speed in the triage screen

 - Content on google drive and version control
 
 - "patch system" needs to set the owner and group ID
 
 - Making this to debian package

 - Talking to Chicago chapter
Sending a network server may be a good idea

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
     
   - For EFI boot, manipulate EFI (DONE)
     Most likely, I should push this to the future because
     90% of computers are still using MBR boot, and 100% of
     computers are MBR bootable.
     - Creating partition using parted - done
     - Creating EFI parition - working

 - Create disk image
   Instead of hardcoding the destination, since there is a UI,
   choose desination possible.
   Disable auto-mount of usb media
   - systemctl mask udisks2

 - Restore disk image - DONE

 - Websocket based reporer for frontend
   - basic plumbing is done. 
   - most things working pretty well

 - http server 
   This is kind of working.
   - serving static file - done
   - serving restore disk - done
   - serving create disk image - done
   - wiping seems working - done
   
 - Disk image directories
   - disk image metadata NEEDS DOC!

 - Supporting parallel execution of restore images.
   - currently sequencial is working. parallel creates a lot of issues. the biggest issue is to manage the resource contention such as CPU usage and bus contention. Payload is gzipped and unzipping requires a lot of CPU power if loading multiple local disks. If single source/multi desination, this needs some plumbing done along with the performance monitoring etc.
   
   
## Frontend
 - Triage UI - in-progress
   Using react.js. First iteration is okay.
   Apparently, it's not intuitive to use this. UX needs to improve.

 - Loading disk image
   - Make the progress rows using individual state in table so the
     state can be updated through websocket.

## Live triage
 - It's sketched out and may be working
 
## Documentation
 - 
 
## Triage app distriubtion


## Content versioning
 - 


## Some other ideas
 - Make the WCE content as separate partition. Since the content is already super compressed, and it's kind of useless to gzip/unzip for save/load. We may able to load the content as single binary blob into partition, and don't bother using partclone or gzip. This has an advantage of mounting the partition as read-only as well. 

## current task

 - Testing out the live triage.
 - UI needs to kill all of FIXME things.
 
