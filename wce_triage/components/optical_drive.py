import os, subprocess, string
from wce_triage.lib.util import *
from wce_triage.components.component import *

tlog = get_triage_logger()

#
# Optical drive class
#
class OpticalDrive(object):
  def __init__(self, device_name, device_node):
    self._device_name = device_name
    self.device_name = '/dev/' + device_name
    self.device_node = device_node
    self.vendor = ''
    self.model_name = ''
    self._detect()
    self.features = []
    pass

  def _detect(self):
    with open(os.path.join(self.device_node, 'device', 'vendor')) as vendor:
      self.vendor = vendor.read().strip()
      pass
    
    with open(os.path.join(self.device_node, 'device', 'model')) as model:
      self.model_name = model.read().strip()
      pass
    pass
    

  # stringify features
  def get_feature_string(self, sep = ' '):
    return sep.join(self.features)

  def debug_print(self):
    fmt = "Device {device}, Features: {feature_list}, Vendor: {vendor}, Model: {model}"
    print(fmt.format(device=self._device_name, feature_list=self.get_feature_string(), vendor=self.vendor, model=self.model))
    pass
  pass


feature_map = {'Can read multisession': ('Multisession', lambda x: int(x) == 1),
               'Can play audio': ('Audio', lambda x: int(x) == 1),
               'Can read CD-R': ('CDR-R', lambda x: int(x) == 1),
               'Can write CD-R': ('CDR-W', lambda x: int(x) == 1),
               'Can write CD-RW': ('CDRW-W', lambda x: int(x) == 1),
               'Can read DVD': ('DVD-R', lambda x: int(x) == 1),
               'Can write DVD-R': ('DVDR-W', lambda x: int(x) == 1),
               'Can write DVD-RAM': ('DVDRAM-W', lambda x: int(x) == 1),
               'Can read MRW': ('MRW-R', lambda x: int(x) == 1),
               'Can write MRW': ('MRW-W', lambda x: int(x) == 1),
               'Can write RAM': ('RAM-W', lambda x: int(x) == 1)}

def detect_optical_drives():
  drives = []
  found = {}
  
  block_device = '/sys/dev/block'

  for dev_id in os.listdir(block_device):
    device_node = os.path.join(block_device, dev_id)
    major = None
    device_name = None
    with open(os.path.join(device_node, 'uevent')) as uevent:
      for line in uevent.readlines():
        tag_value = line.strip().split('=')
        # cd drive is major == 11
        if tag_value[0] == 'MAJOR':
          major = tag_value[1]
          pass
        elif tag_value[0] == 'DEVNAME': # 
          device_name = tag_value[1]
          pass
        pass
      pass

    if major == '11':
      optical = OpticalDrive(device_name, device_node)
      drives.append(optical)
      found[device_name] = optical
      pass
    pass

  # Decorate the found device
  with open('/proc/sys/dev/cdrom/info') as cdrom_info:
    disc = None
    for line in cdrom_info.readlines():
      tag_value = line.strip().split(':')
      if len(tag_value) == 2:
        tag = tag_value[0].strip()
        value = tag_value[1].strip()
        if tag == 'drive name':
          disc = found.get(value)
          pass

        feature = feature_map.get(tag)
        if disc and feature:
          attrname = feature[0]
          value = feature[1](tag_value[1].strip())
          if value:
            disc.features.append(attrname)
            pass
          pass
        pass
      pass
    pass

  return drives


class OpticalDrives(Component):
  
  def __init__(self):
    self._drives = detect_optical_drives()
    pass
  
  def get_component_type(self):
    return "Optical drive"
  
  def count(self):
    return len(self._drives)

  def decision(self, **kwargs):
    decisions = []

    if len(self._drives) == 0:
      decisions.append({ "component": self.get_component_type(),
                          "result": False,
                          "message": "***** NO OPTICALS: INSTALL OPTICAL DRIVE *****" })
    else:
      index = 1
      for optical in self._drives:
        msg = " %d: %s %s %s" % (index, optical.vendor, optical.model_name, optical.get_feature_string(sep=", "))
        decisions.append( {"component": self.get_component_type(),
                           # it's always false until it's tested.
                           "result": False,
                           "device": optical.device_name,
                           "message": msg,
                           "verdict": optical.features })
        index = index + 1
      pass
    return decisions

  

if __name__ == "__main__":
  optical = OpticalDrives()
  print(optical.decision())
  pass
