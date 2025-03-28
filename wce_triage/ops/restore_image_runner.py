#
# Restore disk
#

import sys, uuid, traceback, argparse, os, json

from .tasks import task_fetch_partitions, task_refresh_partitions, task_set_fat_volume_id, task_fsck, task_set_ext_partition_uuid, task_mount, task_unmount, task_remove_persistent_rules, task_finalize_disk, task_install_grub, task_expand_partition, task_finalize_efi

from .ops_ui import console_ui
from .partition_runner import PartitionDiskRunner
from ..components.video import detect_video_cards
from ..components.disk import create_storage_instance
from .partclone_tasks import task_restore_disk_image
from ..lib.util import get_triage_logger
from .json_ui import json_ui
from ..const import const
from .pplan import make_traditional_partition_plan, make_efi_partition_plan, make_usb_stick_partition_plan, EFI_NAME
from ..lib.disk_images import read_disk_image_types


# "Waiting", "Prepare", "Preflight", "Running", "Success", "Failed"]
my_messages = { "Waiting":   "Disk image load is waiting.",
                "Prepare":   "Disk image load is preparing.",
                "Preflight": "Disk image load is preparing.",
                "Running":   "{step} of {steps}: Running {task}",
                "Success":   "Disk image load completed successfully.",
                "Failed":    "Disk image load failed." }

def make_random_hostname(stemname="wce"):
  return stemname + uuid.uuid4().hex[:4]
#
#
class RestoreDiskRunner(PartitionDiskRunner):

  def __init__(self, ui, runner_id, disk, src, src_size, efisrc,
               partition_map=None, 
               partition_id='Linux',
               pplan=None,
               newhostname=None,
               restore_type=None,
               wipe=None,
               media=None,
               wce_share_url=None):
    #
    # FIXME: Well, not having restore type is probably a show stopper.
    #
    if restore_type is None:
      raise Exception('Restore type is not provided.')
    #
    self.partition_id = partition_id
    self.restore_type = restore_type

    efi_boot = self.restore_type.get(const.efi_image) is not None
    partition_plan = self.restore_type.get(const.partition_plan)

    if pplan is None:
      if partition_plan == const.traditional:
        pplan = make_traditional_partition_plan(disk, partition_id=partition_id)
      else:
        pplan = make_efi_partition_plan(disk, partition_id=partition_id)
        pass
      pass

    super().__init__(ui, runner_id, disk, wipe=wipe, partition_plan=pplan, partition_map=partition_map, efi_boot=efi_boot, media=media)

    self.disk = disk
    self.source = src
    self.source_size = src_size
    self.newhostname = newhostname
    self.efi_source = efisrc # EFI partition is pretty small
    self.wce_share_url = wce_share_url
    pass

  def prepare(self):
    # partition runner adds a few tasks to create new partition map.
    super().prepare()

    # This is not true for content loading or cloning
    # FIXME: but what can I do?
    detected_videos = detect_video_cards()

    # sugar
    disk = self.disk
    partition_id = self.partition_id

    # once the partitioning is done, refresh the partition
    self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
    self.tasks.append(task_refresh_partitions("Refresh partition information", disk))

    # load efi
    # hack - source size is hardcoded to 4MB...
    if self.efi_source:
      self.tasks.append(task_restore_disk_image("Load EFI System partition", disk=disk, partition_id=EFI_NAME, source=self.efi_source, source_size=2**22))
      # Loading EFI parition changes the partition ID to the previous volume id. I want to have unique ID so
      # set the ID I have to the EFI partition.
      self.tasks.append(task_set_fat_volume_id("Set EFI partition UUID", disk=disk, partition_id=EFI_NAME))
      # This should now match the previous volume ID so this isn't needed.
      self.tasks.append(task_refresh_partitions("Refresh partition information", disk))
      pass

    # load disk image
    self.tasks.append(task_restore_disk_image("Load disk image", disk=disk, partition_id=partition_id, source=self.source, source_size=self.source_size))

    # Make sure it went right. If this is a bad disk, this should catch it.
    self.tasks.append(task_fsck("fsck partition", disk=disk, partition_id=partition_id, payload_size=self.source_size/4, fix_file_system=True))
    self.tasks.append(task_fsck("fsck partition", disk=disk, partition_id=partition_id, payload_size=self.source_size/4, fix_file_system=True))

    # Loading disk image changes file system's UUID. 
    if self.restore_type["id"] != const.clone:
      # set the fs's uuid to it
      self.tasks.append(task_set_ext_partition_uuid("Set partition UUID", disk=disk, partition_id=partition_id, allow_fail=True))
    else:
      # Read the fs's uuid back
      self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
      pass
    self.tasks.append(task_refresh_partitions("Refresh partition information", disk))

    # expand partition
    self.tasks.append(task_expand_partition("Expand the partition back", disk=disk, partition_id=partition_id))

    # mount it
    self.tasks.append(task_mount("Mount the target disk", disk=disk, partition_id=partition_id))

    # trim some files for new machine
    if self.restore_type["id"] != const.clone:
      self.tasks.append(task_remove_persistent_rules("Remove persistent rules", disk=disk, partition_id=partition_id))
      pass

    # set up some system files. finalize disk sets the new host name and change the fstab
    if self.restore_type["id"] != const.clone:
      self.tasks.append(task_finalize_disk("Finalize disk",
                                           disk=disk,
                                           partition_id=partition_id,
                                           newhostname=self.newhostname,
                                           wce_share_url=self.wce_share_url,
                                           cmdline=self.restore_type.get(const.cmdline)))
      pass

    # Install GRUB
    universal_boot = self.restore_type.get(const.universal_boot, False)
    self.tasks.append(task_install_grub('Install GRUB boot manager', disk=disk,
                                        universal_boot=universal_boot,
                                        detected_videos=detected_videos, partition_id=partition_id))

    # unmount so I can run fsck and expand partition
    if self.restore_type["id"] != const.clone:
      self.tasks.append(task_unmount("Unmount target", disk=disk, partition_id=partition_id))
      pass

    if self.efi_source:
      self.tasks.append(task_mount("Mount the EFI partition", disk=disk, partition_id=EFI_NAME))
      self.tasks.append(task_finalize_efi("Finalize EFI", disk=disk, partition_id=partition_id, efi_id=EFI_NAME))
      self.tasks.append(task_unmount("Unmount the EFI partition", disk=disk, partition_id=EFI_NAME))
      pass
    pass

  pass


def get_source_size(src):
  srcst = os.stat(src)
  return srcst.st_size


#
# Running restore - loading disk image to a disk
#
def run_load_image(ui, devname, imagefile, imagefile_size, efisrc, newhostname, restore_type, wipe, do_it=True):
  '''Loading image to desk.
     :ui: User interface - instance of ops_ui
     :devname: Restroing device name
     :imagefile: compressed partclone image file
     :imagefile_size: Size of image file. If not known, 0 is used.
     :newhostname: New host name assigned to the restored disk. ORIGINAL and RANDOM are special host name.
     :restore_type: dictionary describing the restore parameter. should come from .disk_image_type.json in the image file directory.
     :wipe: 0: no wipe, 1: quick wipe, 2: full wipe
  '''
  # Should the restore type be json or the file?

  disk = create_storage_instance(devname)
  
  id = restore_type.get("id")
  if id is None:
    return
  
  efi_image = restore_type.get(const.efi_image)
  efi_boot=efi_image is not None

  # Get loading media
  media = restore_type.get("media")

  # Interestingly, partition map has no impact on partition plan
  # Partition map in the restore type file is always ignored.
  # FIXME: I'll use it for sanity check
  partition_map = restore_type.get(const.partition_map, "gpt")

  ext4_version = restore_type.get(const.ext4_version)

  # Let's make "triage" id special. This is the only case using usb stick
  # partition plan makse sense.
  # I can use the restore_type parameter but well, this is a sugar.
  # In addition, make usb stick type partition if it is requested.
  #
  # THOUGHTS: Making disk image meta being too complicated is probably not
  # a way to go. It's possible to make everything (parititon map, swap size, etc.)
  # customizable through the metadata but that is going to make things error prone
  # and when something goes wrong, really hard to debug.

  tlog.debug(restore_type)

  if id == "triage" or (restore_type.get(const.partition_plan) == const.triage):
    partition_map = restore_type.get(const.partition_map, 'gpt' if efi_image is not None else 'msdos')
    partition_id = None
    # You can have partition id for gpt, but not for dos partition map
    if partition_map == 'gpt':
      partition_id = 'Linux'
      pplan = make_usb_stick_partition_plan(disk, efi_boot=efi_boot, ext4_version=ext4_version, partition_id=partition_id)
    else:
      pplan = make_usb_stick_partition_plan(disk, efi_boot=efi_boot, ext4_version=ext4_version)
      # For ms-dos partition, you cannot have name so look for the ext4 partition and use
      # the partition number.
      for part in pplan:
        if part.filesys == 'ext4':
          partition_id = part.no
          break
        pass
      pass
    pass
  elif restore_type.get(const.partition_plan) == const.traditional:
    partition_map = restore_type.get(const.partition_map, 'msdos')
    partition_id = None
    # You can have partition id for gpt, but not for dos partition map
    pplan = make_traditional_partition_plan(disk, ext4_version=ext4_version)
    # For ms-dos partition, you cannot have name so look for the ext4 partition and use
    # the partition number.
    for part in pplan:
      if part.filesys == 'ext4':
        partition_id = part.no
        break
      pass
    pass
  else:
    partition_map='gpt'
    partition_id='Linux'
    pplan = make_efi_partition_plan(disk, efi_boot=efi_boot, ext4_version=ext4_version)
    pass

  if partition_id is None:
    tlog.info("Partition ID is missing.")
    for part in pplan:
      tlog.info("Partition %d: name %s, type %s" % (part.no, str(part.name), str(part.partcode)))
      pass
    raise Exception("Partion ID is not known for resotring disk.")
  
  # If new host name is not given, and if restore type asks for new host name,
  # let's do it.
  if newhostname is None:
    newhostname = restore_type.get("hostname")
    if newhostname:
      if restore_type.get("randomize_hostname"):
        newhostname = make_random_hostname(stemname=newhostname)
        tlog.debug("Randomized hostname generated: %s" % newhostname)
        pass
      pass
    pass

  # get wce_share_url from restore_type
  wce_share_url = restore_type.get("wce_share_url")

  disk.detect_disk()

  runner = RestoreDiskRunner(ui, disk.device_name, disk, imagefile, imagefile_size, efisrc,
                             partition_id=partition_id, pplan=pplan, partition_map=partition_map,
                             newhostname=newhostname, restore_type=restore_type, wipe=wipe,
                             media=media, wce_share_url=wce_share_url)
  runner.prepare()
  runner.preflight()
  runner.explain()
  if do_it:
    runner.run()
    pass
  pass


if __name__ == "__main__":
  tlog = get_triage_logger()

  parser = argparse.ArgumentParser(description="Restore Disk image using partclone disk image.")

  parser.add_argument("devname", help="Device name. This is /dev/sdX or /dev/nvmeXnX, not the partition.")
  parser.add_argument("imagesource", help="Image source file. File path or URL.")
  parser.add_argument("imagesize", type=int, help="Size of image. If this the disk image file is on disk, size can be 0, and the loader gets the actual file size.")
  parser.add_argument("restore_type", help="Restore type. This can be a path to the disk image metadata file or a keyword.")

  parser.add_argument("-m", "--hostname", help="new hostname. two keyword can be used for hostname. RANDOM and ORIGINAL")
  parser.add_argument("-p", "--preflight", action="store_true", help="Does preflight only.")
  parser.add_argument("-c", "--cli", action="store_true", help="Creates console UI instead of JSON UI for testing.")
  parser.add_argument("-w", "--fullwipe", action="store_true", help="wipes full disk before partitioning")
  parser.add_argument("--quickwipe", action="store_true", help="wipes first 1MB before partitioning, thus clearning the partition map.")

  args = parser.parse_args()
  
  if args.cli:
    ui = console_ui()
  else:
    ui = json_ui(wock_event="loadimage", message_catalog=my_messages)
    pass

  wipe = None
  if args.fullwipe:
    wipe = 2
  elif args.quickwipe:
    wipe = 1
    pass

  src = args.imagesource
  
  restore_type = args.restore_type

  #
  image_metas = {}
  for image_meta in read_disk_image_types():
    image_metas[image_meta.get("id")] = image_meta
    pass
  
  # Rehydrate the restore_type and make it to Python dict.
  # From Web interface, it should be json string. Only time this is
  # file is when I am typing from terminal for manual restore.
  # Hardcoded ones here are also for testing but I think it describes
  # what should be in the restore type json file
  restore_param: dict = {}
  if isinstance(restore_type, str) and len(restore_type) > 0:
    if restore_type[0] in [".", "/"]:
      with open(restore_type) as json_file:
        restore_param = json.load(json_file)
        pass
      pass
    elif restore_type[0] == "{":
      restore_param = json.loads(restore_type)
      pass
    elif image_metas.get(restore_type):
      restore_param = image_metas[restore_type]
    elif restore_type in [ "wce", "wce-18" ]:
      restore_param = {"id": "wce-18",
                       "filestem": "wce-mate18",
                       "name": "WCE Ubuntu 18.04LTS",
                       "timestamp": True, "efi_image":
                       ".efi-512M.fat32.partclone.gz",
                       "partition_map": "gpt"}
    elif restore_type == "wce-16":
      restore_param = {"id": "wce-16",
                       "filestem": "wce-mate16",
                       "name": "WCE Ubuntu 16.04LTS",
                       "timestamp": True,
                       "ext4_version": "1.42",
                       "partition_map": "gpt"}
    elif restore_type == "triage":
      restore_param ={ "id": "triage",
                       "filestem": "triage",
                       "name": "Triage USB flash drive",
                       "timestamp": True,
                       "efi_image": ".efi-part-32M.fat32.partclone.gz"}
    else:
      ui.log(args.devname, "restore_type is not a file path or json string.")
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
    run_load_image(ui,
                   args.devname,
                   src,
                   args.imagesize,
                   efi_source,
                   args.hostname,
                   restore_param,
                   wipe,
                   do_it=not args.preflight)
    sys.exit(0)
    # NOTREACHED
  except Exception as _exc:
    sys.stderr.write(traceback.format_exc() + "\n")
    sys.exit(1)
    # NOTREACHED
    pass
  pass
