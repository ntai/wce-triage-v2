#
# Video detection
#

if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

from components.pci import *

from collections import namedtuple
Videos = namedtuple('Videos', 'nvidia, ati, vga')

#
#
#
def detect_video_cards():
  n_nvidia = 0
  n_ati = 0
  n_vga = 0
  for pcidev in list_pci():
    if pcidev.device_class == 'video':
      if pcidev.vendor == PCI_VENDOR_NVIDIA:
        # nVidia
        n_nvidia = n_nvidia + 1
        pass
      elif pcidev.vendor == PCI_VENDOR_ATI:
        # ATI
        n_ati = n_ati + 1
        pass
      else:
        n_vga = n_vga + 1
        pass
      pass
    pass
  return Videos(nvidia=n_nvidia, ati=n_ati, vga=n_vga)

#
if __name__ == "__main__":
  print(detect_video_cards())
  pass
  

