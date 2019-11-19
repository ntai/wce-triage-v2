#!/usr/bin/python3
# Copyright (c) 2019 Naoyuki tai
# MIT license - see LICENSE
"""Memory module detection."""

import re, subprocess, os
from .component import Component
from ..lib.util import get_test_password, safe_string

from collections import namedtuple
MemoryInfo = namedtuple('MemoryInfo', 'rams, ramtype, total, slots')

RAM = namedtuple('RAM', 'socket, size, status')
MemorySlot = namedtuple('MemorySlot', 'slot, size, status, memtype')

# DMI type
re_dmi_type = re.compile(r'Handle [\da-fx]+, DMI type (\d+), \d+ bytes')
re_smbios_present = re.compile(r'\s*SMBIOS \d+\.\d+ present.')

def get_memory_size():
  meminfo = open("/proc/meminfo")
  s = int(re.findall("MemTotal:\s+ (\d+) kB\n", meminfo.readline())[0]) / 1024
  meminfo.close()
  return s

#
#
#

class dmi_type_handler(object):
  def start(self):
    raise Exception('dmi_type_handler::start() is not implemented.')

  def parse(self, line):
    raise Exception('dmi_type_handler::parse() is not implemented.')

  def finish(self):
    raise Exception('dmi_type_handler::finish() is not implemented.')

  def get_output(self):
    raise Exception('dmi_type_handler::get_output() is not implemented.')

  pass


# Handler for type 6 - Installed RAM
class dmi_type_handler_6(dmi_type_handler):
  re_memory_module_information = re.compile(r'Memory Module Information')
  re_socket_designation = re.compile(r'\s*Socket Designation: ([\w\d]+)')
  re_enabled_size = re.compile(r'\s*Enabled Size: (\d+) MB')
  re_error_status = re.compile(r'\sError Status: (\w+)')

  def __init__(self):
    self.rams = []
    pass
  

  def start(self, line):
    self.socket_designation = ""
    self.enabled_size = 0
    self.memory_status = True
    pass

  def parse(self, line):
    m = self.re_socket_designation.match(line)
    if m:
      self.socket_designation = m.group(1)
      pass

    m = self.re_enabled_size.match(line)
    if m:
      self.enabled_size = int(m.group(1))
      pass

    m = self.re_error_status.match(line)
    if m:
      self.memory_status = m.group(1).upper() == "OK"
      pass
    pass

  def finish(self):
    self.rams.append(RAM(socket=self.socket_designation, size=self.enabled_size, status=self.memory_status))
    pass

  def get_output(self):
    return self.rams

  pass


# Memory type
class dmi_type_handler_16(dmi_type_handler):
  re_memory_type = re.compile(r'\sType: (\w+)')
  
  def __init__(self):
    self.memory_type = None
    pass

  def start(self, line):
    self.memory_type = None
    pass
    
  def parse(self, line):
    m = self.re_memory_type.match(line)
    if m:
      self.memory_type = m.group(1)
      pass
    pass

  def finish(self):
    pass
  
  def get_output(self):
    return self.memory_type

  pass


# Memory slot
class dmi_type_handler_17(dmi_type_handler):
  # re_memory_device = re.compile(r'Memory Device')

  re_Locator = re.compile(r'^\s*Locator: (\w+)')
  re_Size = re.compile(r'^\s*Size: ((\d+)\s*(\w*)|No Module Installed)')
  re_Type = re.compile(r'^\s*Type: (\w+)')
  re_Manufacturer = re.compile(r'^\s*Manufacturer: (.+)')
  
  def __init__(self):
    self.slots = []
    pass

  def start(self, line):
    self.status = True
    self.slot = None
    self.size = None
    self.memtype = None
    self.manufacturer = None
    pass
  
  def parse(self, line):
    m = self.re_Locator.match(line)
    if m:
      self.slot = m.group(1)
      pass

    m = self.re_Size.match(line)
    if m:
      if m.group(1) != 'No Module Installed':
        try:
          self.size = int(m.group(2))
        except:
          self.size = 0
          self.status = False
          pass
        pass
      else:
        self.size = 0
        self.status = False
        pass
      pass

    m = self.re_Type.match(line)
    if m:
      self.memtype = m.group(1)
      pass

    m = self.re_Manufacturer.match(line)
    if m:
      self.manufacturer = m.group(1)
      pass

    pass

  def finish(self):
    slot = MemorySlot(slot=self.slot, size=self.size, status=self.status, memtype=self.memtype)
    self.slots.append(slot)
    pass

  def get_output(self):
    return sorted(self.slots)

  pass


def _maybe_run_dmidecode():
  """Implementing run dmidecode (maybe)"""
  WCETRIAGE_DMIDECODE_OUTPUT = os.environ.get("WCETRIAGE_DMIDECODE_OUTPUT")
  if WCETRIAGE_DMIDECODE_OUTPUT:
    with open(WCETRIAGE_DMIDECODE_OUTPUT) as test_input:
      return test_input.read()
    pass
  else:
    out = ""
    err = ""

    if os.getuid() != 0:
      cmd = ['sudo', '-H', '-S']
      password = get_test_password()
    else:
      cmd = []
      password = ""
      pass

    cmd = cmd + ['dmidecode', '-t', 'memory']
    dmidecode = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    try:
      (out, err) = dmidecode.communicate(password)
    except Exception as exc:
      pass
    pass
  return out


#
# Get RAM info using dmidecode
#
def get_ram_info():
  """runs 'dmidecode -t memory' command and parses the output to pick off the memory info.

Environ:
WCETRIAGE_DMIDECODE_OUTPUT: If set, reads a text file as dmidecode output for testing.
"""
  out =  _maybe_run_dmidecode()

  parse_state = 0
  dmi_type_handlers = {
    "6": dmi_type_handler_6(),
    "16": dmi_type_handler_16(),
    "17": dmi_type_handler_17(),
  }

  for line in safe_string(out).splitlines():

    if parse_state == 0:
      # Header part
      m = re_smbios_present.match(line)
      if m:
        parse_state = 1
        pass
      pass

    elif parse_state == 1:
      # Indiviual DMI entry
      m = re_dmi_type.search(line)
      if m:
        dmi_type = m.group(1)
        dmi_type_handler = dmi_type_handlers.get(dmi_type)
        if dmi_type_handler:
          dmi_type_handler.start(line)
          pass
        parse_state = 2
        pass
      pass
    elif parse_state == 2:
      
      if len(line.strip()) == 0:
        if dmi_type_handler:
          dmi_type_handler.finish()
          dmi_type_handler = None
          pass
        parse_state = 1
        continue

      if dmi_type_handler:
        dmi_type_handler.parse(line)
        pass
      pass

    pass

  return tuple([ dmi_type_handlers[dmi_type].get_output() for dmi_type in ["16",  "6", "17"]])


#
# Detect the memory nd ram type
#
def detect_memory():
  # Try getting memory from dmidecode
  ram_type, rams, slots = get_ram_info()
  total_memory = 0

  for slot in slots:
    if slot.status:
      total_memory = total_memory + slot.size
      if ram_type is None:
        ram_type = slot.memtype
        pass
      pass
    pass
  
  # backup method
  if total_memory == 0:
    total_memory = get_memory_size()
    pass
  return MemoryInfo(rams=rams, ramtype=ram_type, total=total_memory, slots=slots)


class Memory(Component):
  def __init__(self):
    self.memory = None
    pass

  def get_component_type(self):
    return "Memory"

  def decision(self, **kwargs):
    if self.memory is None:
      self.memory = detect_memory()
      pass
    
    ramtype = self.memory.ramtype if self.memory.ramtype is not None else "Unknown"
    mem_info = "RAM Type: %s  Size: %dMbytes" % (ramtype, self.memory.total)

    decisions = [{"component": self.get_component_type(),
                  "message": mem_info,
                  "result": self.memory.total > 2000}]

    if len(self.memory.slots) > 0:
      slots = ""
      for slot in self.memory.slots:
        slots = slots + " %s: %d MB%s" % (slot.slot, slot.size, " Installed" if slot.status else "")
        pass
      decisions.append({"component": "Memory",
                        "result": True,
                        "message": slots})
      pass
    return decisions

  pass


#
if __name__ == "__main__":
  memory = Memory()
  print(memory.decision())
  pass
