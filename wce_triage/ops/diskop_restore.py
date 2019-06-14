
import * from .diskop
import * from .diskop_tasks

#
# Restroing disk from network
#

class RestoreDiskFromNetwork(DiskOp):
  def __init__(self, ui, disk):
    super.__init__(self, ui)
    self.disk = disk
    pass
  
  def prepare(self):
    self.tasks = [
      task_get_disk_geometry(self, "Get disk geometry", disk=disk),
      task_partition_disk(self, "Get disk geometry", disk=disk, memsize),
      task_mkfs(self, "Initialize partition", disk=disk, partition_id=1),
      task_mkfs(self, "Initialize partition", disk=disk, partition_id=5),

      task_restore_disk_image(self, "Load disk image", disk=disk, partition_id=1, source=image_file),
      task_fsck(self, "Check file system", disk=disk, partition_id=1),
      task_expand_partition(self, "Expand partition", disk=disk, partition_id=1),
      task_fsck(self, "Check file system", disk=disk, partition_id=1),
      task_assign_uuid_to_partition(self, "Assign new UUID to partition", disk=disk, partition_id=1),
      task_assign_uuid_to_partition(self, "Assign new UUID to partition", disk=disk, partition_id=5),
      task_install_grub()
      task_install_bootloader(self, "Install bootloader", disk=disk),
      task_install_mbr(self, "Install MBR", disk=disk),

      task_create_wce_tag(self, "Create WCE release ag", disk=disk, source=image_file)
      ]
    pass

  pass
