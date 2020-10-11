#!/usr/bin/env python3
#
#
from .config_db import triage_config, tag_value_table

pxelinux_cfg_header = """DEFAULT vesamenu.c32
TIMEOUT {timeout}0
TOTALTIMEOUT {total_timeout}0
PROMPT 0
NOESCAPE 1
ALLOWOPTIONS 1
MENU MARGEIN 5

MENU TITLE WCE PXE Triage
"""

pxelinux_cfg_entry = """
LABEL {name}
  MENU LABEL {label}
  KERNEL {kernel}
  APPEND initrd={initrd} hostname=triage64 nosplash noswap boot=nfs netboot=nfs nfsroot={server_ip}:{nfs_root} acpi_enforce_resources=lax edd=on ip=dhcp aufs=tmpfs {cmdline} ---
  TEXT HELP
  {description}
  ENDTEXT
"""

pxelinux_cfg_footer = """
Label Local
  MENU LABEL Local operating system in harddrive (if available)
  KERNEL chain.c32
  APPEND sda1
  TEXT HELP
  Boot local OS from first hard disk if it's available
  ENDTEXT
"""

class pxeboot_config:
  def __init__(self):
    super().__init__(triage_config, "pxeboot")
    pass

  def get_default_pxeboot_entry():
    return { "name": "WCE PXE Triage",
             "label": "WCE ^Triage 64bit",
             "kernel": "wce_amd64/vmlinuz",
             "initrd": "wce_amd64/initrd.img",
             "server_ip": "10.3.2.1",
             "nfs_root": "/var/lib/netclient/wcetriage_amd64",
             "cmdline": "",
             "description": "WCE Triage 64bit (amd64)" }


  def add_pxeboot_entry(self):
    pass
    
  def delete_pxeboot_entry(self, index):
    pass
    

  def provision(self):
    
    self.config = tag_value_table(triage_config, "pxeboot")


    
    
