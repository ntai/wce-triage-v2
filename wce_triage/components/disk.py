import re, sys, os, subprocess, traceback

if __name__ == "__main__":
  sys.path.append(os.path.join(os.getcwd(), ".."))
  pass
from lib.util import *

disk1_re = re.compile(r"Disk /dev/[^:]+:\s+\d+\.\d*\s+[KMG]B, (\d+) bytes")
disk2_re = re.compile(r"\d+ heads, \d+ sectors/track, \d+ cylinders, total (\d+) sectors")
disk3_re = re.compile(r"Units = sectors of \d+ * \d+ = (\d+) bytes")
part_re = re.compile(r"([^\s]+)\s+\*{0,1}\s+\d+\s+\d+\s+\d+\s+([\dA-Fa-f]+)\s+")

wce_release_file_name = 'wce-release'

#
# disk class represents partition
#

class Partition:
  def __init__(self):
    self.device_name = None
    self.partition_name = None
    self.partition_type = None
    self.partition_number = None
    self.partition_uuid = None
    self.mounted = False
    pass

  def get_mount_point(self):
    return "/media/%s" % self.partition_name
    
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
    self.model_name = ""
    self.serial_no = ""
    self.mount_dir = "/mnt/wce_install_target.%d" % os.getpid()
    self.wce_release_file = os.path.join(self.mount_dir, "etc", wce_release_file_name)
    pass


  # find a partition in the partitions
  def find_partition(self, part_id):

    if isinstance(part_id, str):
      for part in self.partitions:
        if part.device_name == part_id:
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
  
  def has_wce_release(self):
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
    self.byte_size = int(size_fd.read())
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

  def detect_disk_type(self):
    # I'm going to be optimistic here since the user can pick a disk
    self.is_disk = False
    self.is_ata_or_scsi = False
    self.is_usb = False

    out = ""
    err = ""
    try:
      cmd = "udevadm info --query=property --name=%s" % self.device_name
      udevadm = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
      (out, err) = udevadm.communicate()
    except Exception as exc:
      traceback.print_exc(sys.stdout)
      pass
      
    if out:
      self.is_disk = True
      for line in safe_string(out).splitlines():
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
            self.disk_model = value
            pass
          elif tag == "ID_SERIAL":
            self.disk_serial = value
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
  pass # End of disk class


#
# Disk operation base class
#
class DiskOp:
  def __init__(self, disk):
    self.disk = disk
    pass
  
  def dispatch(self):
    pass
  pass


#
#
#
def run_detect():
  import computer
  machine = computer.Computer()
  machine.detect_disks()
  for disk in machine.disks:
    print("size=%d" % disk.get_byte_size())
    pass
  pass

if __name__ == "__main__":
  sys.path.append(os.path.join(os.getcwd(), ".."))
  run_detect()
  pass
