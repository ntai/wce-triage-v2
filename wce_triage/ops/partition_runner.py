#!/usr/bin/env python3
#
# Disk operations
#
# Tasks: each task is a disk operation. Some tasks can take a long time.
#
# For example, a task is like mkfs. As the task runs, it should produce progress
#
# By calling into diskop, it creates the plan - which is the sequence of tasks.
# exec runs through the tasks.
#

import datetime, re, subprocess, sys, os

from wce_triage.ops.tasks import *
from wce_triage.ops.ops_ui import *

class PartPlan:
  attribs = ['no', 'name', 'filesys', 'start', 'size', 'parttype', 'flags', 'mkfs_opts']

  def __init__(self, no, name, filesys, start, size, parttype, flags, mkfs_opts):
    self.no = no
    self.name = name
    self.filesys = filesys
    self.start = start
    self.size = size # Size is in MiB
    self.parttype = parttype
    self.flags = flags
    self.mkfs_opts = mkfs_opts
    pass

  def __get__(self, tag):
    if tag not in self.attribs:
      raise("NO %s!" % tag)
    return super().__get__(tag)

  def __set__(self, tag, value):
    if tag not in self.attribs:
      raise("NO %s!" % tag)
    super().__set__(tag, value)
    pass

  pass


def _ext4_version_to_mkfs_opts(ext4_version):
  # extfs 1.42 has no metadata_csum
  return [ '-O', '^metadata_csum'] if ext4_version == "1.42" else None
  

def make_efi_partition_plan(disk, ext4_version=None):
  diskmbsize = int(disk.get_byte_size() / (1024*1024))
  swapsize = int(diskmbsize * 0.05)
  swapsize = 8192 if swapsize > 8192 else (2048 if swapsize < 2048 else swapsize)
  # This is for EFI - yes, still using bios boot. It's coming.

  mkfs_opts = _ext4_version_to_mkfs_opts(ext4_version)

  pplan = [PartPlan(0, None,    None,         0,        2, Partition.MBR,      None,   None),
           PartPlan(1, 'BOOT',  None,         0,       32, Partition.BIOSBOOT, 'boot', None),
           PartPlan(2, 'EFI',   'fat32',      0,      300, Partition.UEFI,     None,   None),
           PartPlan(3, 'SWAP',  'linux-swap', 0, swapsize, Partition.SWAP,     None,   None),
           PartPlan(4, 'Linux', 'ext4',       0,        0, Partition.EXT4,     None,   mkfs_opts) ]
  partion_start = 0
  for part in pplan:
    part.start = partion_start
    if part.size == 0:
      diskmbsize = diskmbsize - 1
      part.size = diskmbsize
      pass
      
    partion_start = partion_start + part.size
    diskmbsize = diskmbsize - part.size
    pass
  return pplan


def make_usb_stick_partition_plan(disk, partition_id=None, ext4_version=None):
  diskmbsize = int(disk.get_byte_size() / (1024*1024))
  # This is for gpt/grub. Set aside the EFI partition so we can 
  # make this usb stick for EFI if needed.
  mkfs_opts = _ext4_version_to_mkfs_opts(ext4_version)
  pplan = [PartPlan(0, None,         None,         0,        2, Partition.MBR,   None,  None),
           PartPlan(1, partition_id, 'ext4',       0,        0, Partition.EXT4, 'boot', mkfs_opts) ]
  partion_start = 0
  for part in pplan:
    part.start = partion_start
    if part.size == 0:
      diskmbsize = diskmbsize - 1
      part.size = diskmbsize
      pass
    partion_start = partion_start + part.size
    diskmbsize = diskmbsize - part.size
    pass
  return pplan


from wce_triage.components.disk import Disk, Partition
from wce_triage.ops.runner import *
#
# create a new gpt partition from partition plan
#
class PartitionDiskRunner(Runner):
  def __init__(self, ui, runner_id, disk, partition_plan, partition_map='gpt'):
    super().__init__(ui, runner_id)
    self.partition_map = partition_map # label is the parted's partition map type
    self.disk = disk
    self.pplan = partition_plan
    pass

  def prepare(self):
    super().prepare()
    # Calling parted
    argv = ['parted', '-s', '-a', 'optimal', self.disk.device_name, 'unit', 'MiB', 'mklabel', self.partition_map]
    for part in self.pplan:
      # Skip MBR
      if part.no == 0:
        continue
      argv = argv + [ arg for arg in [ 'mkpart', 'primary', part.filesys, str(part.start), str(part.start + part.size) ] if arg is not None ]
      # Assign name
      if part.name:
        argv = argv + [ 'name', str(part.no), part.name ]
        pass
      if part.flags:
        for flag in part.flags.split(','):
          argv = argv + ['set', str(part.no), flag, 'on']
          pass
        pass
      pass

    self.tasks.append(op_task_process('Partition disk', argv=argv, time_estimate=5,
                                      progress_finished="Paritions created on %s" % self.disk.device_name))

    for part in self.pplan:
      partdevname = self.disk.device_name + str(part.no)
      partition = Partition(device_name=partdevname,
                            file_system=part.filesys,
                            partition_type=part.parttype,
                            partition_number=part.no)

      if part.filesys in ['fat32', 'ext4']:
        mkfs_desc = "Create file system %s on %s" % (part.filesys, partition.device_name)
        mkfs = task_mkfs(mkfs_desc,
                         partition=partition,
                         progress_finished="mkfs %s on %s completed." % (part.filesys, partition.device_name),
                         time_estimate=4*part.size/1024 + 3,
                         mkfs_opts=part.mkfs_opts)
        self.tasks.append(mkfs)
        mkfs=None
        pass
      elif part.parttype in [Partition.BIOSBOOT, Partition.MBR]:
        # This is a very bad idea.
        #zeropart = task_zero_partition("Clear partition on %s" % partdevname, partition=partition)
        #self.tasks.append(zeropart)
        pass
      elif part.parttype in [Partition.SWAP]:
        mkswap_desc = "Create swap partition on %s" % (partition.device_name)
        mkswap = task_mkswap(mkswap_desc,
                             partition=partition,
                             progress_finished="mkswap on %s completed." % (partition.device_name),
                             time_estimate=3)
        self.tasks.append(mkswap)
        mkswap = None
        pass
      pass
    pass
  pass


if __name__ == "__main__":
  devname = sys.argv[1]
  disk = Disk(device_name=devname)
  ui = console_ui()
  runner = PartitionDiskRunner(ui, disk.device_name, disk, make_usb_stick_partition_plan(disk), partition_map='msdos')
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass

