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
  def __init__(self, ui, disk, destdir):
    super().__init__(ui)
    self.disk = disk
    self.time_estimate = 600
    self.destdir = destdir
    pass

  def prepare(self):
    super().prepare()
    
    # self.tasks.append(task_mount_nfs_destination(self, "Mount the destination volume"))
    # self.tasks.append(task_mount_disk(self, "Mount the target disk", disk=disk, partition_id=1))
    # self.tasks.append(task_remove_persistent_rules(self, "Remote persistent rules", disk=disk, partition_id=1))
    # self.tasks.append(task_unmount(self, "unmount target", disk=disk, partition_id=1))
    # self.tasks.append(task_fsck(self, "fsck partition", disk=disk, partition_id=1))
    # self.tasks.append(task_shrink_partition(self, "shrink partition", disk=disk, partition_id=1))
    # self.tasks.append(task_null(self, "Ready for imaging"))

    self.tasks.append(task_create_disk_image("Creae disk image", disk, stem_name="wce-mate-18", destdir=self.destdir))

    # self.tasks.append(task_extend_partition(self, "expand the partion back", disk=disk, partition_id=1))
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

    linuxpart = self.disk.find_partition("Linux")
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
  devname = sys.argv[1]
  destdir = sys.argv[2]
  disk = Disk(device_name=devname)
  ui = console_ui()
  runner = ImageDisk(ui, disk, destdir)
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass
