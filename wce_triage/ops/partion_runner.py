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

if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

from ops.tasks import *
from ops.ops_ui import *


class PartPlan:
  attribs = ['no', 'name', 'filesys', 'start', 'size', 'parttype', 'flags']

  def __init__(self, no, name, filesys, start, size, parttype, flags):
    self.no = no
    self.name = name
    self.filesys = filesys
    self.start = start
    self.size = size
    self.parttype = parttype
    self.flags = flags
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

def make_efi_partition_plan(disk):
  diskmbsize = int(disk.get_byte_size() / (1024*1024))
  swapsize = int(diskmbsize * 0.05)
  swapsize = 8192 if swapsize > 8192 else (2048 if swapsize < 2048 else swapsize)
  # This is for EFI
  pplan = [PartPlan(0, None,    None,         0,        2, Partition.MBR,  None),
           PartPlan(1, 'BOOT',  None,         0,       32, Partition.BIOSBOOT, 'boot'),
           PartPlan(2, 'EFI',   'fat32',      0,      300, Partition.UEFI, None),
           PartPlan(3, 'SWAP'   'linux-swap', 0, swapsize, Partition.SWAP, None),
           PartPlan(4, 'Linux', 'ext4',       0,        0, Partition.EXT4, None) ]
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


def make_usb_stick_partition_plan(disk):
  diskmbsize = int(disk.get_byte_size() / (1024*1024))
  # This is for gpt/grub. Set aside the EFI partition so we can 
  # make this usb stick for EFI if needed.
  pplan = [PartPlan(0, None,    None,         0,        2, Partition.MBR, None),
           PartPlan(1, 'BOOT',  None,         0,       32, Partition.BIOSBOOT, 'bios_grub'),
           PartPlan(2, 'EFI',   'fat32',      0,      300, Partition.UEFI, None),
           PartPlan(3, 'Linux', 'ext4',       0,        0, Partition.EXT4, None) ]
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


from components.disk import Disk, Partition
from runner import *
#
# create a new gpt partition from partition plan
#
class PartitionDiskRunner(Runner):
  def __init__(self, ui, disk, partition_plan):
    super().__init__(ui)
    self.disk = disk
    self.pplan = partition_plan
    pass

  def prepare(self):
    super().prepare()
    # Calling parted
    argv = ['parted', '-s', '-a', 'optimal', self.disk.device_name, 'unit', 'MiB', 'mklabel', 'gpt']
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

    self.tasks.append(op_task_process('Partition disk', argv=argv, time_estimate=5))

    for part in self.pplan:
      partition = Partition(device_name=disk.device_name + str(part.no),
                            file_system=part.filesys,
                            partition_type=part.parttype,
                            partition_number=part.no)

      if part.filesys in ['fat32', 'ext4']:
        mkfs_desc = "Create file system on %s" % (partition.device_name)
        mkfs = task_mkfs(mkfs_desc,
                         partition=partition,
                         time_estimate=part.size/1024+1)
        self.tasks.append(mkfs)
        pass
      elif part.parttype in [Partition.BIOSBOOT, Partition.MBR]:
        zeropart = task_zero_partition("Clear partition",
                                       partition=partition)
        self.tasks.append(zeropart)
        pass
      pass
    pass



  pass


if __name__ == "__main__":
  devname = sys.argv[1]
  disk = Disk(device_name=devname)
  ui = console_ui()
  runner = PartitionDiskRunner(ui, disk, make_usb_stick_partition_plan(disk))
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass

