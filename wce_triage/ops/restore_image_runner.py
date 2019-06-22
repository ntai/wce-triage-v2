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
import wce_triage.components.video
from wce_triage.ops.partclone_tasks import *
import uuid
from wce_triage.lib.util import is_block_device

#
def make_random_hostname(stemname="wce"):
  return stemname + uuid.uuid4().hex[:8]
#
#
class RestoreDisk(PartitionDiskRunner):

  def __init__(self, ui, disk, src, partition_id='Linux', pplan=None, newhostname=make_random_hostname()):

    #
    self.partition_id = partition_id
    if pplan is None:
      pplan = make_efi_partition_plan(disk, partition_id=partition_id)
      pass

    super().__init__(ui, disk, partition_plan=pplan)

    self.disk = disk
    self.source = src
    self.newhostname = newhostname
    pass

  def prepare(self):
    # partition runner adds a few tasks to create new partition map.
    super().prepare()

    detected_videos = wce_triage.components.video.detect_video_cards()

    # once the partitioning is done, refresh the partition
    self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
    self.tasks.append(task_refresh_partitions("Refresh partition information", disk))

    # load disk image
    self.tasks.append(task_restore_disk_image("Load disk image", disk=self.disk, partition_id=self.partition_id, source=self.source))

    # mount it
    self.tasks.append(task_mount("Mount the target disk", disk=self.disk, partition_id=self.partition_id))

    # trim some files
    self.tasks.append(task_remove_persistent_rules("Remove persistent rules", disk=self.disk, partition_id=self.partition_id))

    # set up some system files
    self.tasks.append(task_finalize_disk("Finalize disk", disk=self.disk, partition_id=self.partition_id, newhostname=self.newhostname))

    # Install GRUB
    self.tasks.append(task_install_grub('Install GRUB boot manager', disk, detected_videos))

    # unmount so I can run fsck and expand partition
    self.tasks.append(task_unmount("Unmount target", disk=self.disk, partition_id=self.partition_id))

    # fsck/expand partition
    self.tasks.append(task_fsck("fsck partition", disk=self.disk, partition_id=self.partition_id))
    self.tasks.append(task_expand_partition("Expand the partion back", disk=self.disk, partition_id=self.partition_id))

    pass

  pass


if __name__ == "__main__":
  if len(sys.argv) == 1:
    print( 'USB Flasher: devname part imagesource')
    sys.exit(0)
    pass
  devname = sys.argv[1]
  if not is_block_device(devname):
    print( '%s is not a block device.' % devname)
    sys.exit(1)
    pass
  part = sys.argv[2]
  src = sys.argv[3]
  disk = Disk(device_name=devname)
  ui = console_ui()
  if part == '1':
    part = 1
    pass
  runner = RestoreDisk(ui, disk, src, partition_id=part, pplan=make_usb_stick_partition_plan(disk), newhostname="wcetriage2")
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass
