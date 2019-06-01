  
class DiskOp_CreateImage(DiskOp):

  def prepare(self):
    self.tasks.append(task_mount_nfs_destination(self, "Mount the destination volume"))
    self.tasks.append(task_mount_disk(self, "Mount the target disk", disk=disk, partition_id=1))
    self.tasks.append(task_remove_persistent_rules(self, "Remote persistent rules", disk=disk, partition_id=1))
    self.tasks.append(task_unmount(self, "unmount target", disk=disk, partition_id=1))
    self.tasks.append(task_fsck(self, "fsck partition", disk=disk, partition_id=1))
    self.tasks.append(task_shrink_partition(self, "shrink partition", disk=disk, partition_id=1))
    self.tasks.append(task_null(self, "Ready for imaging"))
    self.tasks.append(task_create_image_disk(self, "Image disk", disk=disk, partition_id=1))
    self.tasks.append(task_extend_partition(self, "expand the partion back", disk=disk, partition_id=1))
    pass

