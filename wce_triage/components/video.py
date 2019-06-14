#
try:
  from components.pci import *
except:
  from pci import *
  pass

#
# Video device blacklist
# 
# Some VIA UniChrome is not supported by OpenChrome driver
#
video_device_blacklist = { PCI_VENDOR_VIA : { "7205" : True } }

#
#
#
def detect_video_cards():
  n_nvidia = 0
  n_ati = 0
  n_vga = 0
  n_black_vga = 0
  blacklisted_videos = []
  for pci in list_pci():
    if pci['class'] == 'video':
      pci_address = pci['address']
      vendor_id = pci['vendor']
      device_id = pci['device']

      if vendor_id in video_device_blacklist and device_id in video_device_blacklist[vendor_id]:
        blacklisted_videos.append(get_lspci_device_desc(m.group(1)))
        n_black_vga = n_black_vga + 1
      elif vendor_id == PCI_VENDOR_NVIDIA:
        # nVidia
        n_nvidia = n_nvidia + 1
        pass
      elif vendor_id == PCI_VENDOR_ATI:
        # ATI
        n_ati = n_ati + 1
        pass
      else:
        n_vga = n_vga + 1
        pass
      pass
    pass
  return {"nvidia": n_nvidia, "ati": n_ati, "vga": n_vga, "black": n_black_vga, "blacklist": blacklisted_videos}

#
if __name__ == "__main__":
  print(detect_video_cards())
  pass
  

