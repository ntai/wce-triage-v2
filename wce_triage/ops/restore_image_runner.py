#
# Restore disk
#

import datetime, re, subprocess, sys, os, uuid, traceback, logging

from wce_triage.ops.tasks import *
from wce_triage.ops.ops_ui import *
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

  def __init__(self, ui, runner_id, disk, src, src_size, efisrc,
               partition_map=None, 
               partition_id='Linux',
               pplan=None,
               newhostname=make_random_hostname(),
               restore_type=None):
    #
    # FIXME: Well, not having restore type is probably a show stopper.
    #
    if restore_type is None:
      raise Exception('Restore type is not provided.')
    #
    self.partition_id = partition_id
    if pplan is None:
      pplan = make_efi_partition_plan(disk, partition_id=partition_id)
      pass

    self.restore_type = restore_type
    efi_boot = self.restore_type.get('efi_image') is not None
    super().__init__(ui, runner_id, disk, partition_plan=pplan, partition_map=partition_map, efi_boot=efi_boot)

    self.disk = disk
    self.source = src
    self.source_size = src_size
    self.newhostname = newhostname
    self.efi_source = efisrc # EFI partition is pretty small
    pass

  def prepare(self):
    # partition runner adds a few tasks to create new partition map.
    super().prepare()

    # This is not true for content loading or cloning
    # FIXME: but what can I do?
    detected_videos = wce_triage.components.video.detect_video_cards()

    # sugar
    disk = self.disk
    partition_id = self.partition_id

    # load efi
    # hack - source size is hardcoded to 4MB...
    if self.efi_source:
      self.tasks.append(task_restore_disk_image("Load EFI System partition", disk=disk, partition_id=EFI_NAME, source=self.efi_source, source_size=2**22))
      pass

    # once the partitioning is done, refresh the partition
    self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
    self.tasks.append(task_refresh_partitions("Refresh partition information", disk))

    # load disk image
    self.tasks.append(task_restore_disk_image("Load disk image", disk=disk, partition_id=partition_id, source=self.source, source_size=self.source_size))

    # Make sure it went right.
    self.tasks.append(task_fsck("fsck partition", disk=disk, partition_id=partition_id))

    # Loading disk image changes file system's UUID. 
    if self.restore_type["id"] != 'clone':
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
    if self.restore_type["id"] != 'clone':
      self.tasks.append(task_remove_persistent_rules("Remove persistent rules", disk=disk, partition_id=partition_id))
      pass

    # set up some system files. finalize disk sets the new host name and change the fstab
    if self.restore_type["id"] != 'clone':
      self.tasks.append(task_finalize_disk("Finalize disk", disk=disk, partition_id=partition_id, newhostname=self.newhostname))
      pass

    # Install GRUB
    self.tasks.append(task_install_grub('Install GRUB boot manager', disk=disk, detected_videos=detected_videos, partition_id=partition_id))

    # unmount so I can run fsck and expand partition
    if self.restore_type["id"] != 'clone':
      self.tasks.append(task_unmount("Unmount target", disk=disk, partition_id=partition_id))
      pass

    # fsck/expand partition
    self.tasks.append(task_fsck("fsck partition", disk=disk, partition_id=partition_id))
    self.tasks.append(task_expand_partition("Expand the partion back", disk=disk, partition_id=partition_id))

    if self.efi_source:
      self.tasks.append(task_mount("Mount the EFI parttion", disk=disk, partition_id=EFI_NAME))
      self.tasks.append(task_finalize_efi("Finalize EFI", disk=disk, partition_id=partition_id, efi_id=EFI_NAME))
      self.tasks.append(task_unmount("Unmount the EFI parttion", disk=disk, partition_id=EFI_NAME))
      pass
    pass

  pass


def get_source_size(src):
  srcst = os.stat(src)
  return srcst.st_size


#
# Running restore from 
#
def run_load_image(ui, devname, imagefile, imagefile_size, efisrc, newhostname, restore_type, do_it=True):
  '''Loading image to desk.
     :ui: User interface - instance of ops_ui
     :devname: Restroing device name
     :imagefile: compressed partclone image file
     :imagefile_size: Size of image file. If not known, 0 is used.
     :newhostname: New host name assigned to the restored disk.
     :restore_type: dictionary describing the restore parameter. should come from .disk_image_type.json in the image file directory.
  '''
  # Should the restore type be json or the file?
  disk = Disk(device_name = devname)

  id = restore_type.get("id")
  if id is None:
    return
  
  efi_image = restore_type.get("efi_image")
  efi_boot=efi_image is not None

  # Interestingly, partition map has no impact on partition plan
  # Partition map in the restore type file is always ignored.
  # FIXME: I'll use it for sanity check
  partition_map = restore_type.get("partition_map", "gpt")

  ext4_version = restore_type.get("ext4_version")

  # Let's make "triage" id special. This is the only case using usb stick
  # partition plan makse sense.
  # I can use the restore_type parameter but well, this is a sugar.

  if id == "triage":
    partition_map='gpt' if efi_image is not None else 'msdos'
    pplan = make_usb_stick_partition_plan(disk, efi_boot=efi_boot, ext4_version=ext4_version)
    partition_id=1
    pass
  else:
    partition_map='gpt'
    partition_id='Linux'
    pplan = make_efi_partition_plan(disk, efi_boot=efi_boot, ext4_version=ext4_version)
    pass

  runner = RestoreDiskRunner(ui, disk.device_name, disk, imagefile, imagefile_size, efisrc,
                             partition_id=partition_id, pplan=pplan, partition_map=partition_map,
                             newhostname=newhostname, restore_type=restore_type)
  runner.prepare()
  runner.preflight()
  runner.explain()
  if do_it:
    runner.run()
    pass
  pass


if __name__ == "__main__":
  logging.basicConfig(level=logging.DEBUG,
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                      filename='/tmp/triage.log')

  if len(sys.argv) == 1:
    print( 'Flasher: devname imagesource imagesize hostname [preflight] restore_type')
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

  # Preflight is for me to see the tasks. http server runs this with json_ui.
  do_it = True
  if restore_type == "preflight":
    restore_type = sys.argv[6]
    ui = console_ui()
    do_it = False
    pass
  elif restore_type == "testflight":
    restore_type = sys.argv[6]
    ui = console_ui()
    do_it = True
    pass
  else:
    ui = json_ui()
    pass

  # Rehydrate the restore_type and make it to Python dict.
  # From Web interface, it should be json string. Only time this is
  # file is when I am typing from terminal for manual restore.
  # Hardcoded ones here are also for testing but I think it describes
  # what should be in the restore type json file
  if isinstance(restore_type, str) and len(restore_type) > 0:
    if restore_type[0] in [".", "/"]:
      with open(restore_type) as json_file:
        restore_param = json.load(json_file)
        pass
      pass
    elif restore_type[0] == "{":
      restore_param = json.loads(restore_type)
      pass
    elif restore_type in [ "wce", "wce-18" ]:
      restore_param = {"id": "wce-18",
                       "filestem": "wce-mate18",
                       "name": "WCE Ubuntu 18.04LTS",
                       "timestamp": True, "efi_image":
                       ".sda1-efi-part.partclone.gz",
                       "partition_map": "gpt"}
    elif restore_type == "wce-16":
      restore_param = {"id": "wce-16",
                       "filestem": "wce-mate16",
                       "name": "WCE Ubuntu 16.04LTS",
                       "timestamp": True,
                       "ext4_version": "1.42",
                       "partition_map": "gpt"}
    elif restore_type == "triage":
      restore_param ={ "id": "triage", "filestem": "triage", "name": "Triage USB flash drive", "timestamp": True, "efi_image": ".sda1-efi-part.partclone.gz"}
    else:
      ui.log(devname, "restore_type is not a file path or json string.")
      sys.exit(1)
      pass
    pass

  efi_image = restore_param.get("efi_image")
  if efi_image:
    # FIXME: need to think about what to do when the source is URL.
    src_dir = os.path.split(src)[0]
    efi_source = os.path.join(src_dir, efi_image)
  else:
    efi_source = None
    pass
  
  try:
    run_load_image(ui, devname, src, src_size, efi_source, hostname, restore_param, do_it=do_it)
    sys.exit(0)
    # NOTREACHED
  except Exception as exc:
    sys.stderr.write(traceback.format_exc(exc) + "\n")
    sys.exit(1)
    # NOTREACHED
    pass
  pass
