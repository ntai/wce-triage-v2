#!/usr/bin/python3
# Copyright (c) 2019 Naoyuki tai
# MIT license - see LICENSE

import os, subprocess
from wce_triage.components.component import *

def detect_sound_device():
  detected = False
  try:
    for snd_dev in os.listdir("/dev/snd"):
      if snd_dev[0:3] == 'pcm':
        detected = True
        break
      pass
    pass
  except:
    pass
  return detected



class Sound(Component):
  
  def __init__(self):
    self.dev = detect_sound_device()
    pass

  def get_component_type(self):
    return "Sound"

  def decision(self, **kwargs):
    if not self.dev:
      return [{"component": self.get_component_type(),
              "result": False,
              "message": "Sound card: NOT DETECTED -- INSTALL SOUND CARD"}]
      pass
    else:
      return [{"component": self.get_component_type(),
               "result": False,
               "message": "Sound card detected -- Hit [play] button"}]
    pass
  pass


#
if __name__ == "__main__":
  sound = Sound()
  print(sound.decision())
  pass
