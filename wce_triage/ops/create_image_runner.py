#!/usr/bin/env python3
#
# Create disk image
#

import datetime, re, subprocess, sys, os

if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

from ops.partclone_tasks import *
from ops.ops_ui import *
from components.disk import Disk, Partition
from runner import *

#
#
class ImageDisk(Runner):
  def __init__(self, ui, disk, destdir, partition_id = 'Linux'):
    super().__init__(ui)
    self.disk = disk
    self.time_estimate = 600
    self.destdir = destdir
    self.partition_id = partition_id
    pass

  def prepare(self):
    super().prepare()
    
    # self.tasks.append(task_mount_nfs_destination(self, "Mount the destination volume"))

    # self.tasks.append(task_mount(self, "Mount the target disk", disk=disk, partition_id=self.partition_id))
    # self.tasks.append(task_remove_persistent_rules(self, "Remote persistent rules", disk=disk, partition_id=self.partition_id))
    # self.tasks.append(task_unmount(self, "unmount target", disk=disk, partition_id=self.partition_id))
    # self.tasks.append(task_fsck(self, "fsck partition", disk=disk, partition_id=self.partition_id))
    # self.tasks.append(task_shrink_partition(self, "shrink partition", disk=disk, partition_id=self.partition_id))
    # self.tasks.append(task_null(self, "Ready for imaging"))

    self.tasks.append(task_create_disk_image("Creae disk image", disk, partition_id=self.partition_id, stem_name="wce-mate-18", destdir=self.destdir))

    # self.tasks.append(task_extend_partition(self, "expand the partion back", disk=disk, partition_id=self.partition_id))
    pass


  def preflight(self):
    task = task_fetch_partitions("Fetch partitions", self.disk)
    vui = virtual_ui()
    self._run_task(task, vui)
    
    if self.state == RunState.Failed:
      self.ui.print("Fetch partition failed.")
      return

    task = task_refresh_partitions("Refresh partition information", self.disk)
    vui = virtual_ui()
    self._run_task(task, vui)

    if self.state == RunState.Failed:
      self.ui.print("Refresh partition failed.")
      return

    linuxpart = self.disk.find_partition(self.partition_id)
    if linuxpart is None:
      self.state = RunState.Failed
      self.ui.print("Number of partitions = %d" % len(self.disk.partitions))
      for part in self.disk.partitions:
        self.ui.print("%s (%s)" % (part.device_name, part.partition_name))
        pass
      return

    super().preflight()
    pass

  pass

if __name__ == "__main__":
  if len(sys.argv) == 1:
    print( 'devname part destdir')
    sys.exit(0)
    pass
  devname = sys.argv[1]
  part = sys.argv[2]
  destdir = sys.argv[3]
  disk = Disk(device_name=devname)
  ui = console_ui()
  if part == '1':
    part = 1
    pass
  runner = ImageDisk(ui, disk, destdir, partition_id=part)
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass
