#!/usr/bin/python3

import sys, subprocess
from wce_triage.components.disk import PartitionLister, DiskPortal
from wce_triage.lib.util import is_block_device
import uuid

# ID the partition
def find_disk(portal, device_name):
  portal.decision(live_system=True)
  for disk in portal.disks:
    if disk.device_name == device_name:
      return disk
    pass
  return None


def must_end_with_slash(path):
  return path if path[-1] == '/' else path + '/'


if __name__ == "__main__":
  device_name = sys.argv[1]
  if not is_block_device(device_name):
    print(device_name + " is not a block device.")
    sys.exit(1)
    pass

  dst_dir = sys.argv[2]
  
  portal = DiskPortal()
  portal.detect_disks(live_system=False)

  disk = find_disk(portal, device_name)
  if disk is None:
    print("There is no disk named %s." % device_name)
    for disk in portal.disks:
      print(disk.device_name)
      pass
    sys.exit(0)
    pass

  lister = PartitionLister(disk)
  lister.execute()
  part = disk.find_partition('Linux')
  if part is None:
    part = disk.find_partition_by_file_system('ext4')
    pass
  if part is None:
    print("There is no appropriate partition.")
    for part in disk.partitions:
      print(part.partition_name)
      pass
    sys.exit(0)
    pass

  part.fs_uuid = uuid.uuid4().hex
  mount_dir = part.get_mount_point()
  part_dev_name = disk.get_partition_device_file(part.partition_number)
  
  subprocess.run('mkdir -p %s' % mount_dir, shell=True)
  subprocess.run('mount %s %s' % (part_dev_name, mount_dir), shell=True)
  try:
    src_dir = must_end_with_slash(mount_dir)
    dst_dir = must_end_with_slash(dst_dir)
    cmd = 'rsync -av --delete --exclude=var/log --exclude=etc/fstab --exclude=etc/netplan --exclude=home/triage/.cache --exclude=root/.cache --exclude=tmp/--exclude=var/cache/apt/ --exclude=home/triage/.config/pulse/ %s %s' % (src_dir, dst_dir)
    print(cmd)
    sys.stdout.flush()
    subprocess.run(cmd, shell=True)
  finally:
    subprocess.run('umount %s' % (part_dev_name), shell=True)
    subprocess.run('rmdir %s' % (mount_dir), shell=True)
    pass
  sys.exit(0)
