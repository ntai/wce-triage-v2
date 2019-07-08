import os

from wce_triage.components.component import *

from collections import namedtuple
CPUInfo = namedtuple('CPUInfo', 'cpu_class, cores, processors, vendor, model, bogomips, speed')


def parse_cpu_info_tag_value(line):
  elems = line.split(":")
  if len(elems) == 2:
    return (elems[0].strip(), elems[1].strip())
  return (None, None)

def detect_cpu_type():
  '''Detect cpu type.'''
  
  max_processor = 0
  cpu_vendor = "other"
  model_name = ""
  cpu_cores = 1
  cpu_class = 1
  bogomips = 0
  cpu_speed = 0
  cpu_64 = False
  cpu_sse2 = False
  cpu_sse = False
  cpu_3dnow = False
  cpu_mmx = False
  cpu_sse4_2 = False
  
  cpu_info = open("/proc/cpuinfo")
  for line in cpu_info.readlines():
    tag, value = parse_cpu_info_tag_value(line)
    if tag == None:
      continue
    elif tag == "processor":
      processor = int(value)
      if max_processor < processor:
        max_processor = processor
        pass
      pass
    elif tag == 'vendor_id':
      if value == 'GenuineIntel':
        cpu_vendor = "Intel"
      elif value == 'AuthenticAMD':
        cpu_vendor = "AMD"
        pass
      pass
    elif tag == 'cpu MHz':
      cpu_speed = (int)(float(value)+0.5)
      pass
    elif tag == 'model name':
      model_name = value
      pass
    elif tag == 'cpu cores':
      cpu_cores = int(value)
      pass
    elif tag == 'flags':
      
      for a_flag in value.split(' '):
        flag = a_flag.lower()
        if flag == "lm" or flag == "lahf_lm":
          cpu_64 = True
        elif flag == "sse2":
          cpu_sse2 = True
        elif flag == "sse":
          cpu_sse = True
        elif flag == "3dnow":
          cpu_3dnow = True
        elif flag == "mmx":
          cpu_mmx = True
          pass
        elif flag == ["sse4_2" in "sse4a"]:
          cpu_sse4_2 = True
          pass
        pass
      pass
    elif tag == 'bogomips':
      bogomips = value
      pass
    pass
  
  cpu_info.close()
  
  cpu_class = 1
  if cpu_cores >= 2 and cpu_sse4_2:
    cpu_class = 6
  if cpu_cores >= 2:
    cpu_class = 5
  elif cpu_sse2 or (cpu_3dnow and cpu_sse):
    cpu_class = 4
  elif cpu_sse or (cpu_3dnow and cpu_mmx):
    cpu_class = 3
  elif cpu_mmx:
    cpu_class = 2
    pass
  
  # Patch up the CPU speed. cpuinfo seems to show the current CPU speed,
  # not the max speed
  scaling_max_freq = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq"
  if os.path.exists(scaling_max_freq):
    f = open(scaling_max_freq)
    speed = f.read()
    f.close()
    cpu_speed = int(speed) / 1000
    pass
  
  return CPUInfo(**{ "cpu_class": cpu_class, "cores": cpu_cores, "processors": max_processor + 1, "vendor": cpu_vendor, "model": model_name, "bogomips": bogomips, "speed": cpu_speed })


class CPU(Component):
  def __init__(self):
    self.cpu_info = detect_cpu_type()
    pass

  def get_component_type(self):
    return "CPU"

  def decision(self):
    cpu = self.cpu_info
    cpu_detail = "P%d %s %s %dMHz %d cores" % (cpu.cpu_class, cpu.vendor, cpu.model, cpu.speed, cpu.cores)
    return [{"component": self.get_component_type(),
             "result":  self.cpu_info.cpu_class >= 5,
             "message": cpu_detail}]
    pass
  pass

#
if __name__ == "__main__":
  cpu = CPU()
  print(cpu.decision())
  pass
  

