#!/usr/bin/python3
# Copyright (c) 2019 Naoyuki tai
# MIT license - see LICENSE

import subprocess
from wce_triage.lib.util import *

def detect_sensor_modules(modules_path):
  if modules_path:
    modules = open(modules_path)
    lines = modules.readlines()
    modules.close()
    its_there = False
    for line in lines:
      if line == '# LM-SENSORS\n':
        its_there = True
        break
      pass
    if its_there:
      return
    pass

  drivers = []
  sd = subprocess.Popen("cat /dev/null | sensors-detect", shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
  (out, err) = sd.communicate()
  look_for_chip_driver = 0
  for line in safe_string(out).splitlines():
    if look_for_chip_driver == 0:
      if line == '#----cut here----':
        look_for_chip_driver = 1
        pass
      pass
    elif look_for_chip_driver == 1:
      if line == '# Chip drivers':
        look_for_chip_driver = 2
        pass
      pass
    elif look_for_chip_driver == 2:
      if line == '#----cut here----':
        look_for_chip_driver = 0
      else:
        drivers.append(line)
        pass
      pass
    pass

  if len(drivers) > 0:
    if modules_path:
      modules = open(modules_path, 'a+')
      modules.write("# LM-SENSORS\n%s\n#\n" % "\n".join(drivers))
      modules.close()
      pass

    for module in drivers:
      try:
        retcode = subprocess.call("modprobe %s" % module, shell=True)
      except:
        pass
      pass
    pass
  pass


# If setting PWM fails, not a big deal.
def set_pwm(speed):
  p = "/sys/devices/platform"
  re_pwm = re.compile(r'^pwm[0-9]$')
  re_pwm_enable = re.compile(r'^pwm[0-9]_enable$')

  for node in os.listdir(p):
    pnode = os.path.join(p, node)
    nodes = []
    try:
      nodes = os.listdir(pnode)
    except:
      nodes = []
      pass
    for pdev in nodes:
      try:
        if re_pwm.match(pdev):
          ppath = os.path.join(pnode, pdev)
          pwm = open(ppath, "w")
          pwm.write("%d" % speed)
          pwm.close()
          pass
        pass
      except:
        pass
      try:
        if re_pwm_enable.match(pdev):
          ppath = os.path.join(pnode, pdev)
          pwm = open(ppath, "w")
          pwm.write("1")
          pwm.close()
          pass
        pass
      except:
        pass
      pass
    pass
  pass
        
