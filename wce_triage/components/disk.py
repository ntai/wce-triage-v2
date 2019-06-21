import re, sys, os, subprocess, traceback

from wce_triage.lib.util import *

disk1_re = re.compile(r"Disk /dev/[^:]+:\s+\d+\.\d*\s+[KMG]B, (\d+) bytes")
disk2_re = re.compile(r"\d+ heads, \d+ sectors/track, \d+ cylinders, total (\d+) sectors")
disk3_re = re.compile(r"Units = sectors of \d+ * \d+ = (\d+) bytes")
part_re = re.compile(r"([^\s]+)\s+\*{0,1}\s+\d+\s+\d+\s+\d+\s+([\dA-Fa-f]+)\s+")

wce_release_file_name = 'wce-release'

#
# disk class represents partition
#

class Partition:
  MBR = 'EF01'
  BIOSBOOT = 'EF02'
  UEFI = 'EF00'
  SWAP = '8200'
  EXT4 = '8300'

  def __init__(self,
               device_name=None,
               partition_name=None,
               partition_type=None,
               partition_number=None,
               partition_uuid=None,
               fs_uuid=None,
               file_system=None,
               mounted=False):
    self.device_name = device_name
    self.partition_name = partition_name # aka volume name
    self.partition_type = partition_type
    self.partition_number = partition_number
    self.partition_uuid = partition_uuid # Partition UUID, different from fs_uuid
    self.file_system = file_system # This is from parted
    self.fs_uuid = fs_uuid # This is the file system UUID.
    self.mounted = mounted
    pass

  def get_mount_point(self, root='/mnt'):
    return os.path.join(root, self.fs_uuid)
  
  def __str__(self):
    return f"Partition {self.partition_number} on {self.device_name}, name: {self.partition_name}, type: {self.partition_type}, puuid: {self.partition_uuid}, fs: {self.file_system}" 

  pass


#
# disk class represents a disk
#
class Disk:
  def __init__(self, device_name=None):
    self.verdict = False  # True if this is valid disk
    self.device_name = device_name
    self.partitions = []
    self.byte_size = None
    self.sectors = None
    self.mounted = False
    self.partclone_image = "/ubuntu.partclone.gz"
    self.is_disk = None
    self.is_ata_or_scsi = None
    self.is_usb = None
    self.bus = None
    self.model_name = ""
    self.serial_no = ""
    self.mount_dir = "/mnt/wce_install_target.%d" % os.getpid()
    self.wce_release_file = os.path.join(self.mount_dir, "etc", wce_release_file_name)
    pass


  # find a partition in the partitions
  def find_partition(self, part_id):
    if isinstance(part_id, str):
      for part in self.partitions:
        if part.device_name == part_id or part.partition_name == part_id or part.partition_uuid == part_id:
          return part
        pass
      pass
    elif isinstance(part_id, int):
      for part in self.partitions:
        if part.partition_number == part_id:
          return part
        pass
      pass
    return None
  

  # find a partition by partition type
  def find_partition_by_type(self, part_type):
    for part in self.partitions:
      if part.partition_type == part_type:
        return part
      pass
    return None
  

  def has_wce_release(self):
    # FIXME - this + "1" needs to go away
    part1 = self.device_name + "1"
    installed = False
    for partition in self.partitions:
      if partition.partition_name == part1 and partition.partition_type == '83':
        ## print("# %s Partition %s has the linux partition type" % (self.device_name, partition.partition_name))
        # The parition 
        try:
          self.mount_disk()
          if os.path.exists(self.wce_release_file):
            installed = True
            pass
          pass
        except:
          traceback.print_exc(sys.stdout)
          pass
        
        try:
          self.unmount_disk()
          time.sleep(2)
        except:
          traceback.print_exc(sys.stdout)
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
      traceback.print_exc(sys.stdout)
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
          elif tag == "ID_MODEL":
            self.model_name = value
            pass
          elif tag == "ID_SERIAL":
            self.serial_no = value
            pass
          pass
        except:
          traceback.print_exc(sys.stdout)
          pass
        pass
      pass
    else:
      print ()
      self.is_disk = False
      pass
      
    return self.is_disk

  def list_partitions(self):
    return [ str(part) for part in self.partitions ]

  pass # End of disk class

#
#
#
def run_detect():
  import computer
  machine = computer.Computer()
  machine.detect_disks()
  for disk in machine.disks:
    print("device: %s, model: %s, size: %d" % (disk.device_name, disk.model_name, disk.get_byte_size()))
    pass
  pass

if __name__ == "__main__":
  sys.path.append(os.path.join(os.getcwd(), ".."))
  run_detect()
  pass
