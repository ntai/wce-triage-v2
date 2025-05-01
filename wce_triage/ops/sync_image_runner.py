#!/usr/bin/env python3
#
# Create disk image
#

import sys, logging, traceback

from .ops_ui import console_ui
from .runner import Runner
from ..lib.disk_images import get_disk_images
from .json_ui import json_ui
from .sync_image_tasks import task_image_sync_delete, task_image_sync_metadata, task_image_sync_copy, task_image_rsync
from .tasks import task_fetch_partitions, task_refresh_partitions, task_mount, task_unmount
from ..lib.util import is_block_device, get_triage_logger, setup_triage_logger
from ..components.disk import create_storage_instance


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
    self.scoreboard = {}
    pass

  def prepare(self):
    super().prepare()
    
    for disk in self.disks:
      self.scoreboard[disk.device_name] = {"total_size": 0, "completed_size": 0, "inflight_size" : 0, "completed_seconds": 0, "inflight_seconds": 0, "bps": 0}
      pass

    for disk in self.disks:
      self.tasks.append(task_fetch_partitions("Fetch partitions on %s" % disk.device_name , disk=disk))
      self.tasks.append(task_refresh_partitions("Refresh partitions on %s" % disk.device_name, disk=disk))
      self.tasks.append(task_mount("Mount the disk %s" % disk.device_name, disk=disk, partition_id=self.partition_id, add_mount_point=self.add_mount_point))
      pass

    task = task_image_sync_delete("Delete unwanted disk images", keepers=self.sources, testflight=self.testflight)
    self.tasks.append(task)
    self.sync_tasks.append(task)

    for disk in self.disks:
      sync_meta_task = task_image_sync_metadata("Sync metadata on %s" % disk.device_name, disk=disk, testflight=self.testflight)
      self.tasks.append(sync_meta_task)
      self.sync_tasks.append(sync_meta_task)
      pass

    total_size = 0
    for source in self.sources:
      # sync_task = task_image_sync_copy("Copy %s" % source['name'], source=source, testflight=self.testflight, scoreboard=self.scoreboard)
      sync_task = task_image_rsync("Copy %s" % source['name'], source=source, testflight=self.testflight, scoreboard=self.scoreboard)
      self.tasks.append(sync_task)
      self.sync_tasks.append(sync_task)
      total_size += source["size"]
      pass

    for disk in self.disks:
      self.scoreboard[disk.device_name]["total_size"] = total_size
      pass

    for disk in self.disks:
      task = task_unmount("Unmount disk %s" % disk.device_name, disk=disk, partition_id=self.partition_id)
      task.set_teardown_task()
      self.tasks.append(task)
      pass
    pass

  def add_mount_point(self, disk, partition):
    for sync_task in self.sync_tasks:
      sync_task.add_mount_point(disk, partition)
      pass
    pass


  def report_run_state(self):
    sb_fd = open("/tmp/scoreboard", "w")

    for disk in self.disks:
      self.ui.report_run_progress(disk.device_name, self.current_time, self.state, self.run_estimate, self.run_time, self.task_step, self.tasks)

      print("%s:" % disk.device_name, file=sb_fd)
      print(self.scoreboard[disk.device_name], file=sb_fd)
      print("", file=sb_fd)
      pass

    sb_fd.close()

    for task in self.sync_tasks:
      if task._get_status() == 0:
        task.update_time_estimate()
        pass
      pass

    super().report_run_state()
    pass

  def report_task_progress(self, run_time, task):
    for disk in self.disks:
      ui.report_task_progress(disk.device_name, self.current_time, self.run_estimate, run_time, task, self.tasks)
      pass
    pass

  pass


if __name__ == "__main__":
  tlog = get_triage_logger(log_level=logging.DEBUG)

  if len(sys.argv) == 1:
    print( 'SYNC: devicenames [opt] image...')
    sys.exit(0)
    # NOTREACHED
    pass 

  devnames = sys.argv[1]
  sources = sys.argv[2:] # list of image files
  disks = []
  for devname in devnames.split(','):
    if not is_block_device(devname):
      print( '%s is not a block device.' % devname)
      sys.exit(1)
      # NOTREACHED
      pass
    disks.append(create_storage_instance(device_name = devname))
    pass

  # Preflight is for me to see the tasks. http server runs this with json_ui.
  if len(sources) > 0:
    opt = sources[0]
  else:
    opt = None
    pass

  do_it = True
  testflight = False

  if opt == "preflight":
    print("Preflight only.")
    ui = console_ui()
    do_it = False
    sources = sources[1:]
    pass
  elif opt == "testflight":
    print("Should be test flight")
    ui = console_ui()
    do_it = True
    testflight = True
    sources = sources[1:]
    pass
  else:
    if opt == "clean":
      do_it = True
      sources = []
      pass
    ui = json_ui(wock_event="diskimage", message_catalog=my_messages)
    pass

  syncing = []
  runner_id = "diskimage"

  if opt != "clean":
    # Union existing disk images and syncing sources which is subset of disk images.
    # This is to rehydrate the disk image metas.
    disk_images = get_disk_images()
    _sources = {}

    for src in sources:
      _sources[src] = True
      pass

    for disk_image in disk_images:
      if disk_image['name'] in _sources:
        syncing.append(disk_image)
        pass
      pass

    if not syncing:
      tlog.info("Images: " + " ".join([ str(disk_image) for disk_image in disk_images ]))
      tlog.info("Sources: " + " ".join(_sources.keys()))
      raise Exception("no sources?")
    pass

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
  except Exception as _exc:
    sys.stderr.write(traceback.format_exc() + "\n")
    sys.exit(1)
    # NOTREACHED
    pass
  pass
