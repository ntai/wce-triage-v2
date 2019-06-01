import os

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

