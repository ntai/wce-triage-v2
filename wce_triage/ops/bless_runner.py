#
# Bless disk
#

import sys
import traceback
import argparse
import os
import json

from wce_triage.ops.runner import Runner
from .tasks import task_mount, task_unmount, task_remove_persistent_rules, task_finalize_disk, task_install_grub, \
  task_fetch_partitions, task_refresh_partitions

from .ops_ui import console_ui
from ..components.disk import create_storage_instance
from ..lib.util import get_triage_logger
from .json_ui import json_ui
from ..const import const
from .pplan import make_traditional_partition_plan, make_efi_partition_plan, make_usb_stick_partition_plan
from ..lib.disk_images import read_disk_image_types
from .restore_image_runner import make_random_hostname


# "Waiting", "Prepare", "Preflight", "Running", "Success", "Failed"]
my_messages = { "Waiting":   "Disk image load is waiting.",
                "Prepare":   "Disk image load is preparing.",
                "Preflight": "Disk image load is preparing.",
                "Running":   "{step} of {steps}: Running {task}",
                "Success":   "Disk image load completed successfully.",
                "Failed":    "Disk image load failed." }
#
#
class BlessRunner(Runner):
  disk: str  # disk device name
  newhostname: str
  restore_type: dict

  def __init__(self, ui, runner_id: str, disk: str,
               partition_id:str | int='Linux',
               pplan : None | dict = None,
               newhostname: None | str =None,
               restore_type: dict = {}):
    #
    # FIXME: Well, not having restore type is probably a show stopper.
    #
    #
    self.partition_id = partition_id
    self.restore_type = restore_type

    partition_plan = self.restore_type.get(const.partition_plan)

    if pplan is None:
      if partition_plan == const.traditional:
        pplan = make_traditional_partition_plan(disk, partition_id=partition_id)
      else:
        pplan = make_efi_partition_plan(disk, partition_id=partition_id)
        pass
      pass

    super().__init__(ui, runner_id)

    self.disk = disk
    self.newhostname = newhostname
    pass

  def prepare(self):
    super().prepare()

    # sugar
    disk = self.disk
    partition_id = self.partition_id

    # mount it
    self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
    self.tasks.append(task_refresh_partitions("Refresh partition information", disk))
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
                                           newhostname=self.newhostname))
      pass

    # Install GRUB
    videos = (0, 0, 1)
    self.tasks.append(task_install_grub('Install GRUB boot manager', disk=disk, detected_videos=videos, partition_id=partition_id))
    self.tasks.append(task_unmount("Unmount target", disk=disk, partition_id=partition_id))
    pass

  pass


def get_source_size(src):
  srcst = os.stat(src)
  return srcst.st_size


#
# Running restore - loading disk image to a disk
#
def run_bless(ui, devname, newhostname, restore_type, do_it=True):
  '''Loading image to desk.
     :ui: User interface - instance of ops_ui
     :devname: Restroing device name
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

  # Interestingly, partition map has no impact on partition plan
  # Partition map in the restore type file is always ignored.
  # FIXME: I'll use it for sanity check
  # partition_map = restore_type.get(const.partition_map, "gpt")

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


  disk.detect_disk()

  runner = BlessRunner(ui, disk.device_name, disk, partition_id=partition_id,
                       newhostname=newhostname, restore_type=restore_type)

  runner.prepare()
  runner.preflight()
  runner.explain()
  if do_it:
    runner.run()
    pass
  pass


if __name__ == "__main__":
  tlog = get_triage_logger()

  parser = argparse.ArgumentParser(description="Bless disk.")
  parser.add_argument("devname", help="Device name. This is /dev/sdX or /dev/nvmeXnX, not the partition.")
  parser.add_argument("restore_type", help="Restore type. This can be a path to the disk image metadata file or a keyword.")
  parser.add_argument("-m", "--hostname", help="new hostname. two keyword can be used for hostname. RANDOM and ORIGINAL")
  parser.add_argument("-p", "--preflight", action="store_true", help="Does preflight only.")
  parser.add_argument("-c", "--cli", action="store_true", help="Creates console UI instead of JSON UI for testing.")

  args = parser.parse_args()
  if args.cli:
    ui = console_ui()
  else:
    ui = json_ui(wock_event="loadimage", message_catalog=my_messages)
    pass

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

  try:
    run_bless(ui, args.devname, args.hostname, restore_param, do_it=not args.preflight)
    sys.exit(0)
    # NOTREACHED
  except Exception as _exc:
    sys.stderr.write(traceback.format_exc() + "\n")
    sys.exit(1)
    # NOTREACHED
    pass
  pass
