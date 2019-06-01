import re, subprocess, string
from lib.util import *

# Get ram type
re_memory_type = re.compile(r'\sType: (\w+)')
re_memory_device = re.compile(r'Memory Device')
re_physical_memory = re.compile(r'Physical Memory Array')

re_smbios_present = re.compile(r'\s*SMBIOS \d+\.\d+ present.')
re_memory_module_information = re.compile(r'Memory Module Information')

def get_memory_size():
  meminfo = open("/proc/meminfo")
  s = int(re.findall("MemTotal:\s+ (\d+) kB\n", meminfo.readline())[0]) / 1024
  meminfo.close()
  return s

#
# Get RAM info using dmidecode
#
def get_ram_info():
  dmidecode = subprocess.Popen('dmidecode -t 6', shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
  (out, err) = dmidecode.communicate()
  rams = []
  parse_state = 0
  for line in safe_string(out).splitlines():
    if parse_state == 0:
      m = re_smbios_present.match(line)
      if m:
        parse_state = 1
        pass
      pass
    elif parse_state == 1:
      m = re_memory_module_information.match(line)
      if m:
        parse_state = 2
        socket_designation = ""
        enabled_size = 0
        memory_status = True
        pass
      pass
    elif parse_state == 2:
      if len(line.strip()) == 0:
        rams.append( (socket_designation, enabled_size, memory_status) )
        parse_state = 1
        continue

      m = re_socket_designation.match(line)
      if m:
        socket_designation = m.group(1)
        pass

      m = re_enabled_size.match(line)
      if m:
        enabled_size = int(m.group(1))
        pass

      m = re_error_status.match(line)
      if m:
        memory_status = m.group(1).upper() == "OK"
        pass
      pass
    pass
  return rams


def get_ram_type():
  memory_type = None
  dmidecode = subprocess.Popen('dmidecode -t 17', shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
  (out, err) = dmidecode.communicate()
  parse_state = 0
  for line in safe_string(out).splitlines():
    if parse_state == 0:
      m = re_smbios_present.match(line)
      if m:
        parse_state = 1
        pass
      pass
    elif parse_state == 1:
      m = re_memory_device.match(line)
      if m:
        parse_state = 2
        pass
      pass
    elif parse_state == 2:
      if len(line.strip()) == 0:
        parse_state = 1
        continue
      
      m = re_memory_type.match(line)
      if m:
        memory_type = m.group(1)
        pass
      pass
    pass
  
  if memory_type:
    return memory_type
  
  dmidecode = subprocess.Popen('dmidecode -t 16', shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
  (out, err) = dmidecode.communicate()
  if out:
    out = out.decode('utf-8' + '\n')
  else:
    out = ""
    pass
  parse_state = 0
  for line in out.split('\n'):
    if parse_state == 0:
      m = re_smbios_present.match(line)
      if m:
        parse_state = 1
        pass
      pass
    elif parse_state == 1:
      m = re_physical_memory.match(line)
      if m:
        parse_state = 2
        pass
      pass
    elif parse_state == 2:
      if len(line.strip()) == 0:
        parse_state = 1
        continue
      
      m = re_memory_type.match(line)
      if m:
        memory_type = m.group(1)
        pass
      pass
    pass
  
  return memory_type


#
# Detect the memory nd ram type
#
def detect_memory():
  # Try getting memory from dmidecode
  ram_type = get_ram_type()
  rams = get_ram_info()
  total_memory = 0
  for ram in rams:
    total_memory = total_memory + ram[1]
    pass
  # backup method
  if total_memory == 0:
    total_memory = get_memory_size()
    pass
  return { "rams": rams, "ram-type": ram_type, "total": total_memory }


#
if __name__ == "__main__":
  print( str(detect_memory()))
  pass
