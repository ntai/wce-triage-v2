import os, subprocess

def detect_sound_device(hw_info):
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


def detect_sound_device_details():
  pactl = subprocess.run(['pacmd', 'list-sinks'])
  
