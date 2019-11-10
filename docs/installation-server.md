# Installation Server

Mount points wouldn't be controlled

## Network setup

- NIC is either an LAN interfacing or client interfacing
- LAN side is always DHCP? Could be static.
- PXE client side must be static

## Netboot setup

### Package check?

### dnsmasq/PXE

PXE menu imtes need config.

### NFS

- A directory must be exported. default is /var/lib/netclient/wce_triage

### Client root
- After copying kernel (cp /vmlinux /var/lib/netboot/wce_*/), make sure it's world readable. atftpd cannot read it otherwise.
- Updating kernel? Making sure aufs working may be a good idea.
- Updating wce_triage package for the client root
- Updating UI for wce triage app

## Managing disk images

### Disk image metadata

### Disk image files
