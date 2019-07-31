#!/usr/bin/python3
# Copyright (c) 2019 Naoyuki tai
# MIT license - see LICENSE

import re, sys, os, subprocess, traceback, time
import logging

from wce_triage.lib.util import *
from wce_triage.components.component import *

tlog = get_triage_logger()


disk1_re = re.compile(r"Disk /dev/[^:]+:\s+\d+\.\d*\s+[KMG]B, (\d+) bytes")
disk2_re = re.compile(r"\d+ heads, \d+ sectors/track, \d+ cylinders, total (\d+) sectors")
disk3_re = re.compile(r"Units = sectors of \d+ * \d+ = (\d+) bytes")
part_re = re.compile(r"([^\s]+)\s+\*{0,1}\s+\d+\s+\d+\s+\d+\s+([\dA-Fa-f]+)\s+")

wce_release_file_name = 'wce-release'

#
# disk class represents partition
#

class Partition:
  """Partition of disk.

MBR - 'EF01': MBR partition. this isn't really a paritition but 1MB is reserved at the beginning of disk.

BIOSBOOT - 'EF02': BIOS boot partition.
UEFI - 'EF00': EFI system parition. 32MB for our triage USB stick and 512MB for normal use.
SWAP - '8200': Linux swap partition.
EXT4 - '8300': Linux ext4 file system. This can be any version of ext-fs but we only care ext4.
"""

  MBR = 'EF01'
  BIOSBOOT = 'EF02'
  UEFI = 'EF00'
  SWAP = '8200'
  EXT4 = '8300'

  def __init__(self,
               device_name=None,
               partition_name=None,
               partition_type=None, # partition code such as '83'
               partition_number=None,
               partition_uuid=None,
               fs_uuid=None,
               file_system=None,
               mounted=False):
    """ctor of partition.
device_name: Partition device name - ex. /dev/sda1
partition_name: Name of partition - only valid for GPT.
partition_type: partition code such as 82, 83.
partition_number: Parition number - ex 1 for /dev/sda1
partition_uuid: UUID of partition
fs_uuid: UUID of file system
mounted: true if the partition is mounted as file system.
"""
    self.device_name = device_name
    self.partition_name = partition_name # aka volume name
    self.partition_type = partition_type
    self.partition_number = partition_number
    self.partition_uuid = partition_uuid # Partition UUID, different from fs_uuid
    self.file_system = file_system # This is from parted
    self.fs_uuid = fs_uuid # This is the file system UUID.
    self.ext4_version = None # Ext4 file system version. 1.42 is for Ubuntu 16. It added metadata_csum after >= 1.43
    self.mounted = mounted
    pass

  def get_mount_point(self, root='/tmp/mnt'):
    """returns the mount point for the partition.

it's /tmp/mnt/<fs_uuid>.
"""
    return os.path.join(root, self.fs_uuid)
  
  def __str__(self):
    return f"Partition {self.partition_number} on {self.device_name}, name: {self.partition_name}, type: {self.partition_type}, puuid: {self.partition_uuid}, fs: {self.file_system}" 

  pass


#
# disk class represents a disk
#
class Disk:
  def __init__(self, device_name=None, mounted=False):
    self.verdict = False  # True if this is valid disk
    self.device_name = device_name
    self.partitions = []
    self.byte_size = None
    self.sectors = None
    self.mounted = mounted
    self.partclone_image = "/ubuntu.partclone.gz"
    self.is_disk = None
    self.is_ata_or_scsi = None
    self.is_usb = None
    self.bus = None
    self.vendor = ""
    self.model_name = ""
    self.serial_no = ""
    self.mount_dir = "/mnt/wce_install_target.%d" % os.getpid()
    self.wce_release_file = os.path.join(self.mount_dir, "etc", wce_release_file_name)
    self.is_detected = False
    self.disappeared = False
    pass


  # find a partition in the partitions
  def find_partition(self, part_id):
    if isinstance(part_id, str):
      for part in self.partitions:
        if part.device_name == part_id or part.partition_name == part_id or part.partition_uuid == part_id:
          return part
        pass
      if re.match("\d+", part_id):
        try:
          part_id = int(part_id)
        except:
          pass
        pass
      pass

    if isinstance(part_id, int):
      for part in self.partitions:
        if part.partition_number == part_id:
          return part
        pass
      pass
    return None
  

  # get a partition ID that this disk can find.
  def get_partition_id(self, part):
    if part in self.partitions:
      if part.partition_name:
        return part.partition_name
      elif part.partition_number:
        return part.partition_number
      elif part.device_name:
        return part.device_name
      elif part.partition_uuid:
        return part.partition_uuid
      pass
    return None

  # find a partition by partition type
  def find_partition_by_type(self, part_type):
    for part in self.partitions:
      if part.partition_type == part_type:
        return part
      pass
    return None
  

  # find a partition by file system
  # This works only because usually there is only one particular file system.
  # If there are more than one, this would find the first one, and if there
  # are multple, you'd be probably in trouble.
  def find_partition_by_file_system(self, file_system):
    for part in self.partitions:
      if part.file_system == file_system:
        return part
      pass
    return None
  

  def has_wce_release(self):
    # FIXME - this + "1" needs to go away
    part1 = self.device_name + "1"
    installed = False
    for partition in self.partitions:
      if partition.partition_name == part1 and partition.partition_type == '83':
        tlog.debug("%s Partition %s has the linux partition type" % (self.device_name, partition.partition_name))
        # The parition 
        try:
          self.mount_disk()
          if os.path.exists(self.wce_release_file):
            installed = True
            pass
          pass
        except:
          tlog.debug(traceback.format_exc())
          pass
        
        try:
          self.unmount_disk()
          time.sleep(2)
        except:
          tlog.debug(traceback.format_exc())
          pass
        break
      pass
    return installed
  
  
  def get_byte_size(self):
    if self.byte_size is not None:
      return self.byte_size
    size_fd = open("/sys/block/%s/size" % os.path.split(self.device_name)[1])
    self.byte_size = 512*int(size_fd.read())
    size_fd.close()
    return self.byte_size
  
  
  def remove_mount_dir(self):
    if os.path.exists(self.mount_dir) and os.path.isdir(self.mount_dir):
      os.rmdir(self.mount_dir)
      pass
    pass
  
  
  def detect_disk(self):
    if not self.detect_disk_type():
      return False
    self.get_byte_size()
    return True

  # FIXME: may make sense to move this to a task.
  def detect_disk_type(self):
    if self.is_detected:
      return
    self.is_detected = True
    #
    # I'm going to be optimistic here since the user can pick a disk
    self.is_disk = False
    self.is_ata_or_scsi = False
    self.is_usb = False

    out = ""
    err = ""
    try:
      cmd = ['udevadm', 'info', '--query=property', '--name=' + self.device_name]
      udevadm = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', timeout=5)
      out = udevadm.stdout
      err = udevadm.stderr
    except Exception as exc:
      tlog.debug(traceback.format_exc())
      pass
      
    if out:
      self.is_disk = True
      for line in out.splitlines():
        try:
          elems = line.split('=')
          tag = elems[0].strip()
          value = elems[1].strip()
          if tag == "ID_BUS":
            if value.lower() == "ata" or value.lower() == "scsi":
              self.is_ata_or_scsi = True
              pass
            elif value.lower() == "usb":
              self.is_usb = True
              pass
            pass
          elif tag == "ID_TYPE":
            if value.lower() == "disk":
              self.is_disk = True
              pass
            pass
          elif tag == "ID_VENDOR":
            self.vendor = value
            pass
          elif tag == "ID_MODEL":
            self.model_name = value
            pass
          elif tag == "ID_SERIAL":
            self.serial_no = value
            pass
          pass
        except:
          tlog.debug(traceback.format_exc())
          pass
        pass
      pass
    else:
      self.is_disk = False
      pass
      
    return self.is_disk

  def list_partitions(self):
    return [ str(part) for part in self.partitions ]

  pass # End of disk class

# 
#
#
class DiskPortal(Component):

  def __init__(self, live_system=False):
    self.disks = []
    self.detect_disks(live_system=live_system)
    pass

  def get_component_type(self):
    return "Disk"

  #
  # Find out the mounted partitions
  #
  def detect_mounts(self):
    self.mounted_devices = {}
    self.mounted_partitions = {}

    # Known mounted disks. 
    # These cannot be the target
    mount_re = re.compile(r"(/dev/[a-z]+)([0-9]*) ([a-z0-9/\.\-_\+\=,]+) ([a-z0-9]+) (.*)")
    with open('/proc/mounts') as mount_f:
      for one_mount in mount_f.readlines():
        m = mount_re.match(one_mount)
        if m:
          device_name = m.group(1)
          if device_name in self.mounted_devices:
            self.mounted_devices[device_name] = self.mounted_devices[device_name] + ", " + m.group(3)
          else:
            self.mounted_devices[device_name] = m.group(3)
            pass
          partition_name = m.group(1) + m.group(2)
          self.mounted_partitions[partition_name] = m.group(3)
          pass
        pass
      pass
    pass
  

  # live_system is true for live-triage
  # live_system is false for loading and imaging disk
  def detect_disks(self, live_system = True):
    # Know what's mounted already
    self.detect_mounts()

    disk_entry_re = re.compile(r'\s+(\d+)\s+(\d+)\s+([\w\d]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)')

    # Marked first to see it's redetected.
    existing_disks = {}
    for disk in self.disks:
      existing_disks[disk.device_name] = disk
      pass

    added_disks = []
    updated_disks = []
    removed_disks = []

    # Find the disks from diskstats
    with open('/proc/diskstats') as diskstats:
      for disk_entry in diskstats.readlines():
        matched = disk_entry_re.match(disk_entry)
        if matched:
          dev_type = matched.group(1)
          dev_node = matched.group(2)
          dev_name = matched.group(3)

          if dev_type != '8':
            # This is not a disk
            continue

          node_number = int(dev_node)
          if node_number % 16 != 0:
            # This is not a disk node. Rather, is a partition of disk
            continue

          # device name in diskstats has no device file path, so make it up.
          device_name = '/dev/'+dev_name
          is_mounted = device_name in self.mounted_devices
          if is_mounted and (not live_system):
            # Mounted disk %s is not included in the candidate." % device_name
            continue

          disk = existing_disks.get(device_name)
          if disk is None:
            disk = Disk(device_name, mounted=is_mounted)
            if disk.detect_disk():
              self.disks.append(disk)
              added_disks.append(disk)
              pass
            pass
          else:
            # Consume the disk entry
            existing_disks[device_name] = None
            if disk.mounted != is_mounted:
              disk.mounted = is_mounted
              updated_disks.append(disk)
              pass
            pass
          pass
        pass
      pass

    for device_name, disk in existing_disks.items():
      if disk is not None:
        removed_disks.append(disk)
        self.disks.remove(disk)
        pass
      pass
    return (added_disks, updated_disks, removed_disks)

  def count(self):
    return len(self.disks)


  def find_disk_by_device_name(self, device_name):
    for disk in self.disks:
      if disk.device_name == device_name:
        return disk
      pass
    return None


  def decision(self, live_system=False, **kwargs):
    decisions = []
    if self.count() == 0:
      decisions.append( {"component": "Disk", "result": False, "message": "Hard Drive: NOT DETECTED -- INSTALL A DISK"})
    else:
      for disk in self.disks:
        if (not live_system) and disk.mounted:
          continue
        msg = ""
        good_disk = False
        tlog.debug("%s = %d" % (disk.device_name, disk.get_byte_size()))
        disk_gb = disk.get_byte_size() / 1000000000
        disk_msg = "     Device %s: size = %dGbytes  %s" % (disk.device_name, disk_gb, disk.model_name)
        if disk_gb >= 60:
          good_disk = True
          disk_msg += " - Good"
          pass
        else:
          disk_msg += " - TOO SMALL"
          pass
        msg = msg + disk_msg 

        decisions.append( {"component": "Disk",
                           "result": good_disk,
                           "device": disk.device_name,
                           "message": msg})
        pass
      pass
    return decisions
  pass


class PartitionLister:
  #                          1:    2:           3:           4:           5:fs  6:name  7:flags   
  partline_re = re.compile('^(\d+):([\d\.]+)MiB:([\d\.]+)MiB:([\d\.]+)MiB:(\w*):([^:]*):(.*);')

  def __init__(self, disk):
    self.disk = disk
    self.argv = ["parted", "-m", disk.device_name, 'unit', 'MiB', 'print']
    self.out = ""
    pass
  
  def execute(self):
    self.parted = subprocess.run(self.argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self.out = self.parted.stdout.decode('iso-8859-1')
    self.err = self.parted.stderr.decode('iso-8859-1')
    self.parse_parted_output()
    tlog.debug("Lister " + " ".join([ '%s' % arg for arg in self.argv]))
    tlog.debug(self.out)
    tlog.debug(self.err)
    pass

  def set_parted_output(self, out, err):
    self.parted = None
    self.out = out
    self.err = err
    pass

  def parse_parted_output(self):
    self.disk.partitions = []
    partclone_output = self.out.splitlines()
    if partclone_output[0] != 'BYT;':
      raise Exception('parted returned the first line other than BYT; This means the unit printed is not byte.')
    # partclone_output[1] is for whole disk, and unused.
    for line in partclone_output[2:]:
      m = self.partline_re.match(line)
      if m:
        part = Partition(device_name = self.disk.device_name + m.group(1),
                         partition_name = m.group(6),
                         partition_number = int(m.group(1)),
                         file_system = m.group(5))
        self.disk.partitions.append(part)
        pass
      pass
    pass
  pass
#
#
#

if __name__ == "__main__":
  portal = DiskPortal(live_system=True)
  disks = portal.decision(live_system=True)
  for disk in disks:
    print(disk)
    pass
  for disk in portal.disks:
    print("%s is %s" % (disk.device_name, "mounted." if disk.mounted else "not mounted."))
    pass
  
  pass
