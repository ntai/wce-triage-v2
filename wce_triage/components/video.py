#!/usr/bin/python3
# Copyright (c) 2019 Naoyuki tai
# MIT license - see LICENSE

#
# Video detection
#

from .component import Component
from . import pci as _pci

from collections import namedtuple
Videos = namedtuple('Videos', 'nvidia, ati, vga')

#
#
#
def detect_video_cards():
  n_nvidia = 0
  n_ati = 0
  n_vga = 0

  for pcidev in _pci.list_pci():
    if pcidev.device_class == 'video':
      if pcidev.vendor == _pci.PCI_VENDOR_NVIDIA:
        # nVidia
        n_nvidia = n_nvidia + 1
        pass
      elif pcidev.vendor == _pci.PCI_VENDOR_ATI:
        # ATI
        n_ati = n_ati + 1
        pass
      else:
        n_vga = n_vga + 1
        pass
      pass
    pass
  return Videos(nvidia=n_nvidia, ati=n_ati, vga=n_vga)


class Video(Component):
  def __init__(self):
    self.video = detect_video_cards()
    pass

  def get_component_type(self):
    return "Video"

  def decision(self, **kwargs):
    decisions = []
    
    blacklist = _pci.detect_blacklist_devices()
    #
    if len(blacklist.videos) > 0:
      msg = "Remove or disable following video(s) because known to not work\n"
      for video in blacklist.videos:
        msg = msg + "  " + video + "\n"
        pass
      decisions.append({"component": "Video", "result": False, "message": msg})
      pass

    #
    videos = detect_video_cards()
    if (videos.nvidia + videos.ati + videos.vga) >= 0:
      if videos.nvidia > 0:
        decisions.append( {"component": "Video", "result": True, "message": "nVidia video card present" } )
        pass
      if videos.ati > 0:
        decisions.append( {"component": "Video", "result": True, "message": "ATI video card present" } )
        pass
      if videos.vga > 0:
        decisions.append( {"component": "Video", "result": True, "message": "VGA video card present" } )
        pass
      pass
    return decisions
  pass


#
if __name__ == "__main__":
  video = Video()
  print(video.decision())
  pass
  

