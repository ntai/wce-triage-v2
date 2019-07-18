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
from wce_triage.ops.json_ui import *

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
  logging.basicConfig(level=logging.DEBUG,
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                      filename='/tmp/triage.log')

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
  disk = Disk(device_name=devname)

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
  except Exception as exc:
    sys.stderr.write(traceback.format_exc(exc) + "\n")
    sys.exit(1)
    # NOTREACHED
    pass
  pass
