#
# Restore disk
#

import datetime, re, subprocess, sys, os

if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

from wce_triage.ops.tasks import *
from wce_triage.ops.ops_ui import *
from wce_triage.components.disk import Disk, Partition
from wce_triage.ops.runner import *
from wce_triage.ops.partition_runner import *

#
#
class RestoreDisk(PartitionDiskRunner):

  def __init__(self, ui, disk, src):

    #
    self.partition_id = 'Linux'
    pplan = make_usb_stick_partition_plan(disk, partition_id=self.partition_id)

    super().__init__(ui, disk, partition_plan=pplan)

    self.disk = disk
    self.source = src
    self.time_estimate = 600
    pass

  def prepare(self):
    # partition runner adds a few tasks
    super().prepare()

    detected_videos = components.video.detect_video_cards()

    # once the partitioning is done, refresh the partition
    self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
    self.tasks.append(task_refresh_partitions("Refresh partition information", disk))

    # Then mount it
    self.tasks.append(task_mount("Mount the target disk", disk=self.disk, partition_id=self.partition_id))

    # Install GRUB
    self.tasks.append(task_install_grub('Install GRUB boot manager', disk, detected_videos))

    # unmount so I can run restore disk
    self.tasks.append(task_unmount("Unmount target", disk=self.disk, partition_id=self.partition_id))

    # load disk image
    self.tasks.append(task_restore_disk_image("Load disk image", disk=self.disk, partition_id=self.partition_id, source=self.source))

    # expand partition
    self.tasks.append(task_fsck("fsck partition", disk=self.disk, partition_id=self.partition_id))

    # then trim some files
    self.tasks.append(task_remove_persistent_rules("Remove persistent rules", disk=self.disk, partition_id=self.partition_id))
    # update fstab
    # self.tasks.append(task_update_fstab("Update /etc/fstab", disk=self.disk, partition_id=self.partition_id))

    self.tasks.append(task_expand_partition("Expand the partion back", disk=self.disk, partition_id=self.partition_id))

    pass

  pass


if __name__ == "__main__":
  if len(sys.argv) == 1:
    print( 'devname part destdir')
    sys.exit(0)
    pass
  devname = sys.argv[1]
  src = sys.argv[2]
  disk = Disk(device_name=devname)
  ui = console_ui()
  if part == '1':
    part = 1
    pass
  runner = RestoreDisk(ui, disk, src)
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass
