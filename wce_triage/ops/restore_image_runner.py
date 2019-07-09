#
# Restore disk
#

import datetime, re, subprocess, sys, os, uuid, traceback

from wce_triage.ops.tasks import *
from wce_triage.ops.ops_ui import *
from wce_triage.components.disk import Disk, Partition
from wce_triage.ops.runner import *
from wce_triage.ops.partition_runner import *
import wce_triage.components.video
from wce_triage.ops.partclone_tasks import *
from wce_triage.lib.util import is_block_device
from wce_triage.ops.json_ui import *

#
def make_random_hostname(stemname="wce"):
  return stemname + uuid.uuid4().hex[:8]
#
#
class RestoreDiskRunner(PartitionDiskRunner):

  def __init__(self, ui, runner_id, disk, src, src_size, partition_id='Linux', pplan=None, newhostname=make_random_hostname(), partition_map='gpt', restore_type=None):

    #
    self.restore_type = restore_type if restore_type is not None else 'wce'
    self.partition_id = partition_id
    if pplan is None:
      pplan = make_efi_partition_plan(disk, partition_id=partition_id)
      pass

    super().__init__(ui, runner_id, disk, partition_plan=pplan, partition_map=partition_map)

    self.disk = disk
    self.source = src
    self.source_size = src_size
    self.newhostname = newhostname
    pass

  def prepare(self):
    # partition runner adds a few tasks to create new partition map.
    super().prepare()

    # This is not true for content loading or cloning
    detected_videos = wce_triage.components.video.detect_video_cards(None)

    # sugar
    disk = self.disk
    partition_id = self.partition_id

    # once the partitioning is done, refresh the partition
    self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
    self.tasks.append(task_refresh_partitions("Refresh partition information", disk))

    # load disk image
    self.tasks.append(task_restore_disk_image("Load disk image", disk=disk, partition_id=partition_id, source=self.source, source_size=self.source_size))

    # Make sure it went right.
    self.tasks.append(task_fsck("fsck partition", disk=disk, partition_id=partition_id))

    # Loading disk image changes file system's UUID. 
    if self.restore_type != 'clone':
      # set the fs's uuid to it
      self.tasks.append(task_set_partition_uuid("Set partition UUID", disk=disk, partition_id=partition_id))
    else:
      # Read the fs's uuid back
      self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
      self.tasks.append(task_refresh_partitions("Refresh partition information", disk))
      pass

    # mount it
    self.tasks.append(task_mount("Mount the target disk", disk=disk, partition_id=partition_id))

    # trim some files for new machine
    if self.restore_type != 'clone':
      self.tasks.append(task_remove_persistent_rules("Remove persistent rules", disk=disk, partition_id=partition_id))
      pass

    # set up some system files. finalize disk sets the new host name and change the fstab
    if self.restore_type != 'clone':
      self.tasks.append(task_finalize_disk("Finalize disk", disk=disk, partition_id=partition_id, newhostname=self.newhostname))
      pass

    # Install GRUB
    self.tasks.append(task_install_grub('Install GRUB boot manager', disk=disk, detected_videos=detected_videos, partition_id=partition_id))

    # unmount so I can run fsck and expand partition
    if self.restore_type != 'clone':
      self.tasks.append(task_unmount("Unmount target", disk=disk, partition_id=partition_id))
      pass

    # fsck/expand partition
    self.tasks.append(task_fsck("fsck partition", disk=disk, partition_id=partition_id))
    self.tasks.append(task_expand_partition("Expand the partion back", disk=disk, partition_id=partition_id))

    pass

  pass


def get_source_size(src):
  srcst = os.stat(src)
  return srcst.st_size



def run_load_image(ui, devname, imagefile, imagefile_size, newhostname, restore_type, do_it=True):
  disk = Disk(device_name = devname)

  if restore_type == "triage":
    pplan = make_usb_stick_partition_plan(disk)
    partition_id=1
    partition_map='msdos'
  else:
    # ext4 1.42 didn't have metadata_csum. mkfs needs extra options to disable the feature
    # denote it as "wce-16", therefore, translate "wce-16" to "ext4 version 1.42".
    # Newer ones have no need for the mkfs opts
    pplan = make_efi_partition_plan(disk, ext4_version = ("1.42" if restore_type == 'wce-16' else None))
    partition_id='Linux'
    partition_map='gpt'
    pass

  runner = RestoreDiskRunner(ui, disk.device_name, disk, imagefile, imagefile_size, 
                             pplan=pplan, partition_id=partition_id, partition_map=partition_map,
                             newhostname=newhostname, restore_type=restore_type)
  runner.prepare()
  runner.preflight()
  runner.explain()
  if do_it:
    runner.run()
    pass
  pass


if __name__ == "__main__":
  if len(sys.argv) == 1:
    print( 'Flasher: devname imagesource imagesize hostname [wce|wce-16|triage|clone|preflight]')
    sys.exit(0)
    # NOTREACHED
    pass 
  devname = sys.argv[1]
  if not is_block_device(devname):
    print( '%s is not a block device.' % devname)
    sys.exit(1)
    # NOTREACHED
    pass

  src = sys.argv[2]
  src_size = int(sys.argv[3])
  if src_size == 0:
    src_size = get_source_size(src)
  hostname = sys.argv[4]
  restore_type = sys.argv[5]

  do_it = True
  if restore_type == "preflight":
    restore_type = sys.argv[6]
    ui = console_ui()
    do_it = False
    pass
  else:
    ui = json_ui()
    pass

  try:
    run_load_image(ui, devname, src, src_size, hostname, restore_type, do_it=do_it)
    sys.exit(0)
    # NOTREACHED
  except Exception as exc:
    sys.stderr.write(traceback.format_exc(exc) + "\n")
    sys.exit(1)
    # NOTREACHED
    pass
  pass
