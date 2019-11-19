#!/usr/bin/env python3
"""clone_runner.py

Clone runner does cloning/binary copying of disk.
This is because making USB stick is panifully slow, and binary copy is 
10+x faster.


"""

import sys

from .tasks import op_task_wipe_disk, op_task_process, task_sync_partitions, task_mkfs, task_mkswap
from .ops_ui import console_ui
from .pplan import make_usb_stick_partition_plan
from ..components.disk import create_storage_instance, Partition
from .runner import Runner
from ..lib.util import init_triage_logger

tlog = init_triage_logger()

#
# create a new gpt partition from partition plan
#
class CloneRunner(Runner):
  def __init__(self, ui, runner_id, disk=None, partition_map=None, partition_plan=None, wipe=None, media=None, **kwargs):
    super().__init__(ui, runner_id, **kwargs)
    self.disk = disk
    self.partition_map = partition_map
    self.pplan = partition_plan
    self.efi_boot = efi_boot
    self.wipe = wipe
    self.media = media
    pass

  def prepare(self):
    super().prepare()

    # wipe?
    if self.wipe == 1 or self.wipe == 2:
      if self.wipe == 1:
        desc = "Wipe first 1Mb of disk"
      else:
        desc = "Wipe whole disk"
        pass
      self.tasks.append(op_task_wipe_disk(desc, disk=self.disk, short=(self.wipe == 1)))
      pass

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

    # After creating partitions, let kernel sync up and create device files.
    # Pretty often, the following mkfs fails due to kernel not acknowledging the
    # new partitions and partition device file not read for the follwing mkks.
    # NOTE: pplan includes boot part which is not partition so subtract 1
    self.tasks.append(task_sync_partitions('Sync partitions', time_estimate=3,
                                           disk=self.disk, n_partitions=len(self.pplan)-1))

    for part in self.pplan:
      partdevname = self.disk.device_name + str(part.no)
      partition = Partition(device_name=partdevname,
                            file_system=part.filesys,
                            partcode=part.partcode,
                            partition_number=part.no)

      if part.filesys in ['fat32', 'vfat', 'ext4']:
        mkfs_desc = "Create file system %s (%d) on %s" % (part.filesys, part.size, partition.device_name)
        part_byte_size = part.size * 2**10
        if part.filesys == 'ext4':
          estimate_size = (part_byte_size/2)
        else:
          estimate_size = 16 * 2**10
          pass
        mkfs = task_mkfs(mkfs_desc,
                         partition=partition,
                         progress_finished="mkfs %s on %s completed." % (part.filesys, partition.device_name),
                         time_estimate=3 + estimate_size/self.disk.estimate_speed("mkfs"),
                         mkfs_opts=part.mkfs_opts,
                         media=self.media)
        self.tasks.append(mkfs)
        mkfs=None
        pass
      elif part.partcode == Partition.BIOSBOOT:
        # Don't clear part
        #zeropart = task_zero_partition("Clear partition on %s" % partdevname, partition=partition)
        #self.tasks.append(zeropart)
        pass
      elif part.partcode == Partition.MBR:
        # Don't clear part
        pass
      elif part.partcode in [Partition.SWAP]:
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
  disk = create_storage_instance(device_name=devname)
  efi_boot = True
  part_map = 'gpt' if efi_boot else 'msdos'
  ui = console_ui()
  runner = CloneRunner(ui, disk.device_name, disk, make_usb_stick_partition_plan(disk, efi_boot=efi_boot), partition_map=part_map)
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass

