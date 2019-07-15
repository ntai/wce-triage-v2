#!/usr/bin/env python3
#
# Create disk image
#

import datetime, re, subprocess, sys, os

from wce_triage.ops.partclone_tasks import *
from wce_triage.ops.ops_ui import *
from wce_triage.components.disk import Disk, Partition
from wce_triage.ops.runner import *
from wce_triage.lib.disk_images import *

#
class ImageDiskRunner(Runner):
  def __init__(self, ui, runner_id, disk, destdir, suggestedname=None, partition_id='LINUX'):
    super().__init__(ui, runner_id)
    self.time_estimate = 600
    self.disk = disk
    self.partition_id = partition_id
    self.destdir = destdir

    self.imagename = make_disk_image_name(destdir, suggestedname)
    pass


  def prepare(self):
    super().prepare()
    
    # self.tasks.append(task_mount_nfs_destination(self, "Mount the destination volume"))
    self.tasks.append(task_fetch_partitions("Fetch partitions", self.disk))
    self.tasks.append(task_refresh_partitions("Refresh partition information", self.disk))

    self.tasks.append(task_mount("Mount the target disk", disk=self.disk, partition_id=self.partition_id))
    self.tasks.append(task_remove_persistent_rules("Remove persistent rules", disk=self.disk, partition_id=self.partition_id))
    task = task_unmount("Unmount target", disk=self.disk, partition_id=self.partition_id)
    task.set_teardown_task()
    self.tasks.append(task)
    self.tasks.append(task_fsck("fsck partition", disk=self.disk, partition_id=self.partition_id))
    self.tasks.append(task_shrink_partition("Shrink partition to smallest", disk=self.disk, partition_id=self.partition_id))
    self.tasks.append(task_create_disk_image("Create disk image", disk=self.disk, partition_id=self.partition_id, imagename=self.imagename))
    task = task_expand_partition("Expand the partion back", disk=self.disk, partition_id=self.partition_id)
    task.set_teardown_task()
    self.tasks.append(task)
    pass

  pass

if __name__ == "__main__":
  if len(sys.argv) == 1:
    print( 'devicename part destdir')
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
  runner_id = disk.device_name
  runner = ImageDiskRunner(ui, runner_id, disk, destdir, partition_id=part)
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass
