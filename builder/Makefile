.PHONY: clean

# Domains built by builder.py (--name defaults have changed over time -
# ubuntu-server was the old Ubuntu Server default, xubuntu is current) and
# vm_from_device.py (wce-triage-device).
VMS = ubuntu-server xubuntu wce-triage-device

# Force-stops and undefines each VM, deleting its disk(s) too (--remove-all-storage
# only removes volumes libvirt manages, e.g. the default pool at
# /var/lib/libvirt/images - which is where builder.py's disks live). Safe to
# run even if a domain was never created or is already gone.
clean:
	for vm in $(VMS); do \
		sudo virsh destroy $$vm 2>/dev/null || true; \
		sudo virsh undefine $$vm --remove-all-storage 2>/dev/null || true; \
	done
