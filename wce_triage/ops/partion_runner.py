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
  attribs = ['no', 'filesys', 'start', 'size', 'parttype', 'flags']

  def __init__(self, no, filesys, start, size, parttype, flags):
    self.no = no
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

MBR = 0
EFI_system = 1
SWAP = 2
EXT4 = 3

from components.disk import Disk, Partition
from runner import *

#
# Base class for disk operations
#
class PartitionDiskRunner(Runner):
  def __init__(self, ui, disk):
    super().__init__(ui)
    self.disk = disk
    diskmbsize = int(self.disk.get_byte_size() / (1024*1024))
    swapsize = int(diskmbsize * 0.05)
    swapsize = 8192 if swapsize > 8192 else (2048 if swapsize < 2048 else swapsize)
    self.pplan = [PartPlan(0, None,         0,        1, MBR, None),
                  PartPlan(1, 'fat32',      0,        1, EFI_system, 'boot,esp'),
                  PartPlan(2, 'linux-swap', 0, swapsize, SWAP, None),
                  PartPlan(3, 'ext4',       0,        0, EXT4, None) ]
    partion_start = 0
    for part in self.pplan:
      part.start = partion_start
      if part.size == 0:
        diskmbsize = diskmbsize - 1
        part.size = diskmbsize-1
        pass
      
      partion_start = partion_start + part.size
      diskmbsize = diskmbsize - part.size
      pass
    pass

  def prepare(self):
    super().prepare()
    argv = ['parted', '-s', '-a', 'optimal', '/dev/' + self.disk.device_name, 'unit', 'MiB', 'mklabel', 'gpt']
    for part in self.pplan:
      # Skip MBR
      if part.no == 0:
        continue
      argv = argv + [ arg for arg in [ 'mkpart', 'primary', part.filesys, str(part.start), str(part.start + part.size) ] if arg is not None ]
      if part.flags:
        for flag in part.flags.split(','):
          argv = argv + ['set', str(part.no), flag, 'on']
          pass
        pass
      pass
    self.tasks.append(op_task_process('Partition disk', argv=argv, time_estimate=5))

    for part in self.pplan:
      if part.parttype == EXT4:
        partition = Partition(device_name=disk.device_name + str(part.no),
                              partition_type='83',
                              partition_number=part.no)
        mkfs_desc = "Create EXT4 file system on %s%d" % (disk.device_name, part.no)
        mkfs = task_mkfs(mkfs_desc,
                         partition=partition,
                         time_estimate=part.size/1024+1)
        self.tasks.append(mkfs)
        pass
      pass
    pass

  pass

if __name__ == "__main__":
  devname = sys.argv[1]
  disk = Disk(device_name=devname)
  ui = console_ui()
  runner = PartitionDiskRunner(ui, disk)
  runner.prepare()
  runner.preflight()
  runner.explain()
  pass

