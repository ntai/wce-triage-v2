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
from wce_triage.ops.pplan import *
from wce_triage.components.disk import Disk, Partition
from wce_triage.ops.runner import *
from wce_triage.lib.util import *
#
# create a new gpt partition from partition plan
#
class PartitionDiskRunner(Runner):
  def __init__(self, ui, runner_id, disk, partition_plan, partition_map='gpt', efi_boot=False):
    super().__init__(ui, runner_id)
    self.partition_map = partition_map # label is the parted's partition map type
    self.disk = disk
    self.pplan = partition_plan
    self.efi_boot = efi_boot
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

    tlog.debug("parted: " + str(argv))
    self.tasks.append(op_task_process('Partition disk', argv=argv, time_estimate=5,
                                      progress_finished="Paritions created on %s" % self.disk.device_name))

    # After creting partitions, let kernel sync up and create device files.
    # Pretty often, the following mkfs fails due to kernel not acknowledging the
    # new partitions and partition device file not read for the follwing mkks.
    argv = ['partprobe']
    tlog.debug("partprobe: " + str(argv))
    self.tasks.append(op_task_process_simple('Sync partitions', argv=argv, time_estimate=1,
                                             progress_finished="Partitions synced with kernel"))

    for part in self.pplan:
      partdevname = self.disk.device_name + str(part.no)
      partition = Partition(device_name=partdevname,
                            file_system=part.filesys,
                            partition_type=part.parttype,
                            partition_number=part.no)

      if part.filesys in ['fat32', 'vfat', 'ext4']:
        mkfs_desc = "Create file system %s on %s" % (part.filesys, partition.device_name)
        mkfs = task_mkfs(mkfs_desc,
                         partition=partition,
                         progress_finished="mkfs %s on %s completed." % (part.filesys, partition.device_name),
                         time_estimate=4*part.size/1024 + 3,
                         mkfs_opts=part.mkfs_opts)
        self.tasks.append(mkfs)
        mkfs=None
        pass
      elif part.parttype == Partition.BIOSBOOT:
        # Don't clear part
        #zeropart = task_zero_partition("Clear partition on %s" % partdevname, partition=partition)
        #self.tasks.append(zeropart)
        pass
      elif part.parttype == Partition.MBR:
        # Don't clear part
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
  efi_boot = True
  part_map = 'gpt' if efi_boot else 'msdos'
  ui = console_ui()
  runner = PartitionDiskRunner(ui, disk.device_name, disk, make_usb_stick_partition_plan(disk, efi_boot=efi_boot), partition_map=part_map)
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass

