#!/usr/bin/env python3
#
import typing
from typing import List, Optional

from pydantic import BaseModel

from ..components.disk import Partition
from ..const import const

EFI_NAME = 'EFI_System_Partition'
EFI_PART_OPT ='boot,esp'
BIOS_GRUB_OPT = 'bios_grub'


class PartPlan(BaseModel):
  no: int
  name: Optional[str] = None
  filesys: Optional[str] = None
  start: int = 0
  size: int              # Size is in MiB; 0 means "flex" - size_partitions() fills in the remainder.
  partcode: str
  flags: Optional[str] = None
  mkfs_opts: Optional[List[str]] = None
  pass


def _ext4_version_to_mkfs_opts(ext4_version):
  # extfs 1.42 has no metadata_csum
  return [ '-O', '^metadata_csum'] if ext4_version == const.ext4_version_1_42 else None
  

#
def size_partitions(pplan: typing.List[Partition], diskmbsize):
  """Do simple math on partitions and figure out the size of partitions."""
  part0: typing.Optional[Partition] = None
  for part in pplan:
    if part.size == 0:
      if part0 is not None:
        raise Exception("cannot have two flex size partitions.")
      part0 = part
      continue
    diskmbsize = diskmbsize - part.size
    pass

  if part0:
    diskmbsize = diskmbsize - 1
    part0.size = diskmbsize
    pass
  
  partion_start = 0
  for part in pplan:
    part.start = partion_start
    partion_start = partion_start + part.size
    pass

  return pplan

#
# This is univeral partition plan, should work for efi or traditional boot.
# I think Ubuntu 18.04LTS and up should use EFI boot.
# 
def make_efi_partition_plan(disk, ext4_version=None, efi_boot=False, partition_id=None):
  diskmbsize = int(disk.get_byte_size() / (1024*1024))

  # Use up to 5% of disk for swap, but max of 8GB.
  # Smallest swap size is 2GB.
  swapsize = min(8192, max(2048, int(diskmbsize * 0.05)))

  mkfs_opts = _ext4_version_to_mkfs_opts(ext4_version)

  if efi_boot:
    bios_part_opt = BIOS_GRUB_OPT
    efi_part_opt = EFI_PART_OPT
  else:
    bios_part_opt = 'boot'
    efi_part_opt = None
    pass

  if partition_id is None:
    partition_id = 'Linux'
    pass

  pplan = [PartPlan(no=0, name=None,        filesys=None,         start=0, size=2,        partcode=Partition.MBR,      flags=None,          mkfs_opts=None),
           PartPlan(no=1, name='BOOT',      filesys=None,         start=0, size=32,       partcode=Partition.BIOSBOOT, flags=bios_part_opt, mkfs_opts=None),
           PartPlan(no=2, name=EFI_NAME,    filesys='fat32',      start=0, size=512,      partcode=Partition.UEFI,     flags=efi_part_opt,  mkfs_opts=None),
           PartPlan(no=3, name='SWAP',      filesys='linux-swap', start=0, size=swapsize, partcode=Partition.SWAP,     flags=None,          mkfs_opts=None),
           PartPlan(no=4, name=partition_id, filesys='ext4',      start=0, size=0,        partcode=Partition.EXT4,     flags=None,          mkfs_opts=mkfs_opts) ]

  return size_partitions(pplan, diskmbsize)


#
# This is traditional (non-EFI) partition boot.
# Old machines may need this with DOS partition.
# 
def make_traditional_partition_plan(disk, ext4_version=None, partition_id=None):
  diskmbsize = int(disk.get_byte_size() / (1024*1024))
  # Use up to 5% of disk for swap, but stop at 8GB. 
  swapsize = int(diskmbsize * 0.05)
  swapsize = 8192 if swapsize > 8192 else (2048 if swapsize < 2048 else swapsize)
  mkfs_opts = _ext4_version_to_mkfs_opts(ext4_version)
  bios_part_opt = 'boot'
  #efi_part_opt = None

  pplan = [PartPlan(no=0, name=None, filesys=None,         start=0, size=2,        partcode=Partition.MBR,      flags=None,          mkfs_opts=None),
           PartPlan(no=1, name='BOOT', filesys=None,       start=0, size=32,       partcode=Partition.BIOSBOOT, flags=BIOS_GRUB_OPT, mkfs_opts=None),
           PartPlan(no=2, name=None, filesys='ext4',       start=0, size=0,        partcode=Partition.EXT4,     flags=bios_part_opt, mkfs_opts=mkfs_opts),
           PartPlan(no=3, name=None, filesys='linux-swap', start=0, size=swapsize, partcode=Partition.SWAP,     flags=None,          mkfs_opts=None) ]
  return size_partitions(pplan, diskmbsize)


#
# This is traditional partition boot.
# Old machines may need this with DOS partition.
# 
def make_usb_stick_partition_plan(disk, partition_id=None, ext4_version=None, efi_boot=False):
  diskmbsize = int(disk.get_byte_size() / (1024*1024))
  # This is for gpt/grub. Set aside the EFI partition so we can 
  # make this usb stick for EFI if needed.
  mkfs_opts = _ext4_version_to_mkfs_opts(ext4_version)

  if efi_boot:
    pplan = [PartPlan(no=0, name=None,         filesys=None,    start=0, size=2,  partcode=Partition.MBR,      flags=None,         mkfs_opts=None),
             # For desktop and Windows, etc., the EFI partition is 512MiB but for USB stick,
             # it's only for installation. 32MiB is plenty big.
             PartPlan(no=1, name='BOOT',       filesys=None,    start=0, size=32, partcode=Partition.BIOSBOOT, flags=BIOS_GRUB_OPT, mkfs_opts=None),
             PartPlan(no=2, name=EFI_NAME,     filesys='fat32', start=0, size=32, partcode=Partition.UEFI,     flags=EFI_PART_OPT,  mkfs_opts=None),
             PartPlan(no=3, name=partition_id, filesys='ext4',  start=0, size=0,  partcode=Partition.EXT4,     flags=None,          mkfs_opts=mkfs_opts) ]
  else:
    pplan = [PartPlan(no=0, name=None,         filesys=None,   start=0, size=2,  partcode=Partition.MBR,      flags=None,          mkfs_opts=None),
             PartPlan(no=1, name='BOOT',       filesys=None,   start=0, size=32, partcode=Partition.BIOSBOOT, flags=BIOS_GRUB_OPT, mkfs_opts=None),
             PartPlan(no=2, name=partition_id, filesys='ext4', start=0, size=0,  partcode=Partition.EXT4,     flags='boot',        mkfs_opts=mkfs_opts) ]
    pass
  return size_partitions(pplan, diskmbsize)


def print_pplan(pplan):
  """Print pplan for testing/debugging"""
  for part in pplan:
    print(f"Part {part.no} - {part.name}: fs {part.filesys}, start {part.start}, size {part.size}, partcode {part.partcode}, flags {part.flags}, mkfs {part.mkfs_opts}")
    pass
  pass
