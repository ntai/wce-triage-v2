#!/usr/bin/env python3
#
# Create disk image
#

import datetime, re, subprocess, sys, os, logging

from .partclone_tasks import *
from .ops_ui import *
from ..components.disk import create_storage_instance
from .runner import *
from ..lib.disk_images import *
from .json_ui import *
from .sync_image_tasks import *
from .run_state import *


# "Waiting", "Prepare", "Preflight", "Running", "Success", "Failed"]
my_messages = { "Waiting":   "Syncing disk image is waiting.",
                "Prepare":   "Syncing disk image is preparing.",
                "Preflight": "Syncing disk image is preparing.",
                "Running":   "{step} of {steps}: Running {task}",
                "Success":   "Syncing disk image completed successfully.",
                "Failed":    "Syncing disk image failed." }

#
class SyncImageRunner(Runner):
  '''Runner for creating disk image. does fsck, shrink partition, create disk 
image and resize the file system back to the max.
For now, this is only dealing with the EXT4 linux partition.
'''
  def __init__(self, ui, runner_id, sources, disks, testflight=False):
    super().__init__(ui, runner_id)
    self.sources = sources # This is a list of dict from get_disk_images()
    self.time_estimate = 600
    self.disks = disks
    self.partition_id = 'Linux'
    self.sync_tasks = []
    self.testflight = testflight
    print("Test flight" if self.testflight else "Real flight")
    pass

  def prepare(self):
    super().prepare()
    
    for disk in self.disks:
      self.tasks.append(task_fetch_partitions("Fetch partitions", disk=disk))
      self.tasks.append(task_refresh_partitions("Refresh partitions", disk=disk))
      self.tasks.append(task_mount("Mount the target disk", disk=disk, partition_id=self.partition_id, add_mount_point=self.add_mount_point))
      pass

    task = task_image_sync_delete("Delete unwanted disk images", keepers=self.sources, testflight=self.testflight)
    self.tasks.append(task)
    self.sync_tasks.append(task)

    for source in self.sources:
      sync_task = task_image_sync_copy("Copy disk image", source=source, testflight=self.testflight)
      self.tasks.append(sync_task)
      self.sync_tasks.append(sync_task)
      pass

    for disk in self.disks:
      task = task_unmount("Unmount target", disk=disk, partition_id=self.partition_id)
      task.set_teardown_task()
      self.tasks.append(task)
      pass
    pass

  def add_mount_point(self, disk, partition):
    for sync_task in self.sync_tasks:
      sync_task.add_mount_point(disk, partition)
      pass
    pass

  pass


if __name__ == "__main__":
  tlog = init_triage_logger(log_level=logging.DEBUG)

  if len(sys.argv) == 1:
    print( 'SYNC: images devicenames opt')
    sys.exit(0)
    # NOTREACHED
    pass 

  sources = sys.argv[1] # list of image files
  devnames = sys.argv[2]
  disks = []
  for devname in devnames.split(','):
    if not is_block_device(devname):
      print( '%s is not a block device.' % devname)
      sys.exit(1)
      # NOTREACHED
      pass
    disks.append(Disk(device_name = devname))
    pass

  # Preflight is for me to see the tasks. http server runs this with json_ui.
  if len(sys.argv) >= 4:
    opt = sys.argv[3]
  else:
    opt = devnames
    pass

  print(opt)

  do_it = True
  testflight = False
  if opt == "preflight":
    ui = console_ui()
    do_it = False
    pass
  elif opt == "testflight":
    print("Should be test flight")
    ui = console_ui()
    do_it = True
    testflight = True
    pass
  else:
    ui = json_ui(wock_event="diskimage", message_catalog=my_messages)
    pass

  # Union existing disk images and syncing sources which is subset of disk images.
  # This is to rehydrate the disk image metas.
  disk_images = get_disk_images()
  _sources = {}
  for src in sources.split(','):
    _sources[src] = True
    pass

  syncing = []
  for disk_image in disk_images:
    if disk_image['name'] in _sources:
      syncing.append(disk_image)
      pass
    pass

  runner_id = "diskimage"
  runner = SyncImageRunner(ui, runner_id, syncing, disks, testflight=testflight)
  try:
    runner.prepare()
    runner.preflight()
    runner.explain()
    if do_it:
      runner.run()
      pass
    sys.exit(0)
    # NOTREACHED
  except Exception as exc:
    sys.stderr.write(traceback.format_exc(exc) + "\n")
    sys.exit(1)
    # NOTREACHED
    pass
  pass
