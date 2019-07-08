#!/usr/bin/env python3

from wce_triage.components.component import *
from wce_triage.components import pci as _pci
from wce_triage.components import cpu as _cpu
from wce_triage.components import memory as _memory
from wce_triage.components import network as _network
from wce_triage.components import disk as _disk
from wce_triage.components import video as _video
from wce_triage.components import sound as _sound
from wce_triage.components import optical_drive as _optical_drive

import re, subprocess, os, sys, json

re_socket_designation = re.compile(r'\s*Socket Designation: ([\w\d]+)')
re_enabled_size = re.compile(r'\s*Enabled Size: (\d+) MB')
re_error_status = re.compile(r'\sError Status: (\w+)')


from wce_triage.lib.util import *
from wce_triage.components.disk import Disk, Partition

tlog = get_triage_logger()


class Computer(Component):
  def __init__(self):
    self.target = None # Installation destination

    #
    self.decisions = []
    self.decision = None
    pass

  #
  # TRIAGE
  # 

  def gather_info(self):

    self.cpu = _cpu.CPU()
    self.memory = _memory.Memory()
    #
    self.disk_portal = _disk.DiskPortal()
    #
    self.video = _video.Video()
    #
    self.networks = _network.Networks()

    self.sound = _sound.Sound()

    self.opticals = _optical_drive.OpticalDrives()

    self.components = [ self.cpu, self.memory, self.video, self.disk_portal, self.opticals, self.networks, self.sound]
    pass


  def triage(self, live_system = False):
    self.gather_info();
    self.make_decision()
    return self.decision

  def make_decision(self):
    #
    for component in self.components:
      self.decisions = self.decisions + component.decision()
      pass

    self.decision = True
    for decision in self.decisions:
      if not decision.get("result"):
        self.decision = False
        break
      pass
    return

  # This may be too invasive...
  def update_decision( self, keys, updates, overall_changed = None):
    for decision in self.decisions:
      matched_decision = decision

      for key, value in keys.items():
        if decision.get(key) != value:
          matched_decision = None
          break
        pass
      
      if matched_decision:
        break
      pass

    if matched_decision:
      tlog.debug( "Updating %s with %s" % (matched_decision["component"], str(updates)))
      for key, value in updates.items():
        if key == 'message':
          matched_decision[key] = value + " " + matched_decision[key]
        else:
          matched_decision[key] = value
          pass
        pass
      pass
    else:
      tlog.debug( "Not updating %s with %s. THIS IS PROBABLY A BUG." % (str(keys), str(updates)))
      pass

    new_decision = True
    for decision in self.decisions:
      if not decision.get("result"):
        new_decision = False
        break
      pass

    if new_decision != self.decision:
      self.decision = new_decision
      if overall_changed:
        overall_changed(new_decision)
        pass
      pass
    pass
  
  # End of computer class
  pass


if __name__ == "__main__":
  computer = Computer()
  decision = computer.triage()
  print( "decision %s" % decision)
  for detail in computer.decisions:
    print(detail)
    pass
  pass
