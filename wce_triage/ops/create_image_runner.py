#!/usr/bin/env python3
#
# Create disk image
#

import re, sys, traceback

from .tasks import (task_fetch_partitions, task_refresh_partitions, task_mount, task_remove_persistent_rules,
                    task_remove_logs, task_fsck, task_shrink_partition, task_expand_partition, task_unmount,
                    task_remove_triage_home_cache)
from .partclone_tasks import task_create_disk_image
from .ops_ui import console_ui
from ..components.disk import create_storage_instance
from .runner import Runner
from ..lib.disk_images import make_disk_image_name
from .json_ui import json_ui
from ..lib.util import get_triage_logger, is_block_device

# "Waiting", "Prepare", "Preflight", "Running", "Success", "Failed"]
my_messages = { "Waiting":   "Saving disk is waiting.",
                "Prepare":   "Savign disk is preparing.",
                "Preflight": "Saving disk is preparing.",
                "Running":   "{step} of {steps}: Running {task}",
                "Success":   "Saving disk completed successfully.",
                "Failed":    "Saving disk failed." }

#
class ImageDiskRunner(Runner):
  '''Runner for creating disk image. does fsck, shrink partition, create disk 
image and resize the file system back to the max.
For now, this is only dealing with the EXT4 linux partition.
'''
  # FIXME: If I want to make this to a generic clone app, I need to deal with all of partitions on the disk.
  # One step at a time.
    
  def __init__(self, ui, runner_id, disk, destdir, suggestedname=None, partition_id='Linux'):
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
    self.tasks.append(task_remove_triage_home_cache("Remove persistent rules", disk=self.disk, partition_id=self.partition_id))
    self.tasks.append(task_remove_persistent_rules("Remove persistent rules", disk=self.disk, partition_id=self.partition_id))
    self.tasks.append(task_remove_logs("Remove/Clean Logs", disk=self.disk, partition_id=self.partition_id))
    task = task_unmount("Unmount target", disk=self.disk, partition_id=self.partition_id)
    task.set_teardown_task()
    self.tasks.append(task)
    self.tasks.append(task_fsck("fsck partition", disk=self.disk, partition_id=self.partition_id, fix_file_system=True))
    self.tasks.append(task_shrink_partition("Shrink partition to smallest", disk=self.disk, partition_id=self.partition_id))
    self.tasks.append(task_create_disk_image("Create disk image", disk=self.disk, partition_id=self.partition_id, imagename=self.imagename))

    task = task_expand_partition("Expand the partition back", disk=self.disk, partition_id=self.partition_id)
    task.set_teardown_task()
    self.tasks.append(task)
    pass

  pass


if __name__ == "__main__":
  tlog = get_triage_logger()

  if len(sys.argv) == 1:
    print( 'Unloader: devicename part destdir')
    sys.exit(0)
    # NOTREACHED
    pass

  devname = sys.argv[1]
  if not is_block_device(devname):
    print( '%s is not a block device.' % devname)
    sys.exit(1)
    # NOTREACHED
    pass

  part = sys.argv[2] # This is a partition id
  destdir = sys.argv[3] # Destination directory
  disk = create_storage_instance(devname)

  # Preflight is for me to see the tasks. http server runs this with json_ui.
  do_it = True
  if destdir == "preflight":
    ui = console_ui()
    do_it = False
    pass
  elif destdir == "testflight":
    ui = console_ui()
    do_it = True
    pass
  else:
    ui = json_ui(wock_event="saveimage", message_catalog=my_messages)
    pass

  if re.match(part, '\d+'):
    part = int(part)
    pass

  runner_id = disk.device_name
  runner = ImageDiskRunner(ui, runner_id, disk, destdir, partition_id=part)
  try:
    runner.prepare()
    runner.preflight()
    runner.explain()
    runner.run()
    sys.exit(0)
    # NOTREACHED
  except Exception as _exc:
    sys.stderr.write(traceback.format_exc() + "\n")
    sys.exit(1)
    # NOTREACHED
    pass
  pass
