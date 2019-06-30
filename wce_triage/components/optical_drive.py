import os, subprocess, string
from wce_triage.lib.util import *
from wce_triage.lib.hwinfo import *

#
# Find optical device files
#

def find_optical_device_files(devpath = None):
  if devpath is None: 
    devpath = "/dev/sr"
    pass
  result = []
  for letter in "0123456789":
    device_file = devpath + letter
    if os.path.exists(device_file):
      result.append(device_file)
    else:
      break
    pass
  return result


#
# Optical drive class
#
class OpticalDrive(object):
  def __init__(self, device_name="unknown", is_cd=True, is_dvd=False, model_name="", vendor="", features=[]):
    if isinstance(device_name, list):
      for devname in device_name:
        if os.path.islink(devname):
          continue
        self.device_name = devname
        break
      pass
    else:
      self.device_name = device_name
      pass

    self.features = features
    self.model_name = model_name
    self.vendor = vendor
    self.is_cd = is_cd
    self.is_dvd = is_dvd
    pass

  def __getattribute__(self, key):
    if key == 'model':
      key = 'model_name'
    elif key == 'device':
      key = 'device_name'
    elif key == 'feature_list':
      return self.get_feature_string()
    elif key == 'cd':
      return "y" if self.is_cd else "n"
    elif key == 'dvd':
      return "y" if self.is_dvd else "n"
    return object.__getattribute__(self, key)

  def __setattr__(self, key, value):
    if key == 'model':
      key = 'model_name'
      pass
    elif key == 'device':
      key = 'device_name'
      pass
    object.__setattr__(self, key, value)
    pass


  # stringify featues
  def get_feature_string(self, sep = ' '):
    self.features.sort()
    cd = []
    dvd = []
    rest = []
    for feature in self.features:
      if feature[0:2] == "CD":
        if len(feature[2:]) > 0:
          cd.append(feature[2:])
          pass
        else:
          cd.append("CD")
          pass
        pass
      elif feature[0:3] == "DVD":
        if len(feature[3:]) > 0:
          dvd.append(feature[3:])
          pass
        else:
          dvd.append("DVD")
          pass
        pass
      else:
        rest.append(feature)
        pass
      pass
    features = []
    if len(cd) > 0:
      features.append(" ".join(cd))
      pass
    if len(dvd) > 0:
      features.append(" ".join(dvd))
      pass
    return ", ".join(features + rest)

  # detect the device is optical or not
  def detect(self):
    self.features = []
    self.is_cd = False
    self.is_dvd = False
    self.vendor = ""
    self.model_name = ""

    out = ""
    try:
      cmd = "udevadm info --query=property --name=%s" % self.device_name
      udevadm = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
      (out, err) = udevadm.communicate()
      out = safe_string(out)
      err = safe_string(err)
    except Exception as exc:
      self.is_cd = False
      self.is_dvd = False
      out = ""
      err = str(exc)
      pass

    for line in out.splitlines():
      elems = line.split('=')
      if len(elems) != 2:
        continue
      tag = elems[0].strip()
      value = elems[1].strip()
      if tag == "ID_TYPE":
        if value.lower() == "cd":
          self.is_cd = True
          pass
        pass
      elif tag == "ID_CDROM":
        if value == "1":
          self.is_cd = True
          pass
        pass
      elif tag[0:9] == "ID_CDROM_":
        self.is_cd = True
        if value == "1":
          feature = tag[9:].replace('_', '-')
          if feature == "DVD-PLUS-R":
            self.is_dvd = True
            self.features.append("DVD+R")
          elif feature == "DVD-PLUS-RW":
            self.is_dvd = True
            self.features.append("DVD+RW")
          elif feature == "DVD-PLUS-R-DL":
            self.is_dvd = True
            self.features.append("DVD+R(DL)")
          else:
            if feature[0:3] == 'DVD':
              self.is_dvd = True
              pass
            self.features.append(feature)
            pass
          pass
        pass
      elif tag == "ID_VENDOR":
        self.vendor = value
      elif tag == "ID_MODEL":
        self.model_name = value
        pass
      pass
    return self.is_cd

  def debug_print(self):
    fmt = "Device {device}, CD: {cd}, DVD: {dvd}, Features: {feature_list}, Vendor: {vendor}, Model: {model}"
    print(fmt.format(device=self.device, cd=self.cd, dvd=self.dvd, feature_list=self.feature_list, vendor=self.vendor, model=self.model))
    pass
  pass


def detect_optical_drives(hw_info):
  drives = []
  if hw_info:
    storages = hw_info.get_entries('storage')
    if storages is None:
      print("no storage")
      return drives
      
    for storage in storages:
      children = storage.get('children')
      if children is None:
        continue
      for child in children:
        if child.get("class") != "disk":
          continue
        capabilities = child.get("capabilities")
        if capabilities is None:
          continue
        # If disk that cannot read cd-r, this is not optical drive.
        if not capabilities.get('cd-r'):
          continue
        disc = child
        logicalname = child.get("logicalname")
        drives.append(OpticalDrive(logicalname,
                                 is_dvd=capabilities.get("dvd") is not None,
                                 vendor=disc.get("vendor"),
                                 model_name=disc.get("product"),
                                 features = [feature.upper() for feature in capabilities.keys() ]))
        break
      pass
    return drives
  
  for optical in find_optical_device_files():
    current_optical = OpticalDrive(optical)
    if current_optical.detect():
      drives.append(current_optical)
      pass
    pass
  return drives

  
if __name__ == "__main__":
  for opt in detect_optical_drives(hw_info()):
    opt.debug_print()
    pass

  for optical in find_optical_device_files():
    current_optical = OpticalDrive(optical)
    is_optical = current_optical.detect()
    current_optical.debug_print()
    pass
  pass

