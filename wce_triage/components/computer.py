#!/usr/bin/python3
# Copyright (c) 2019 Naoyuki tai
# MIT license - see LICENSE
from typing import Callable

from .component import Component
# from . import pci as _pci
from . import cpu as _cpu
from . import memory as _memory
from . import network as _network
from . import disk as _disk
from . import video as _video
from . import sound as _sound
from . import optical_drive as _optical_drive
from . import power as _power

import re

re_socket_designation = re.compile(r'\s*Socket Designation: ([\w\d]+)')
re_enabled_size = re.compile(r'\s*Enabled Size: (\d+) MB')
re_error_status = re.compile(r'\sError Status: (\w+)')

from ..lib.util import get_triage_logger

tlog = get_triage_logger()


class Computer(Component):
  """Computer class.

Computer is a component but also an aggregator of all of components on the computer.
"""

  def __init__(self):
    self.target = None # Installation destination

    #
    self.live_system = False
    self.decisions = []
    self.decision = None
    pass

  #
  # TRIAGE
  # 

  def gather_info(self):
    """gathers info of computer.

As a aggregator of components, it calls into the device detections and accumulates the info.
"""

    self.cpu = _cpu.CPU()
    self.memory = _memory.Memory()
    #
    self.disk_portal = _disk.DiskPortal(live_system=self.live_system)
    #
    self.video = _video.Video()
    #
    self.networks = _network.Networks()

    self.sound = _sound.Sound()

    self.opticals = _optical_drive.OpticalDrives()

    self.power = _power.PowerSupply()

    self.components = [ self.cpu, self.memory, self.video, self.disk_portal, self.opticals, self.networks, self.sound, self.power]
    pass


  def triage(self, live_system = False) -> bool:
    """gathers info of computer, and decides the overall triage status.

arg: live_system -> bool

live_system denotes this triage is done for live system.
The difference between live/non-live system is, the mounted disk counts for live system while non-live triage excludes the monted disk.
"""

    # live_system denotes this triage is done for live system
    # The difference between live/non-live system is, the mounted disk
    # counts for live system while non-live triage excludes the monted disk.
    self.live_system = live_system
    self.gather_info();
    self.make_decision()
    return self.decision

  def make_decision(self):
    """making decision based on the components' decision. 

Each component has its own decision, and the computer honors it.
Overall decision (self.decision) is True only when every component decision is good.
"""
    
    #
    for component in self.components:
      self.decisions = self.decisions + component.decision(live_system=self.live_system)
      pass

    self.decision = True
    for decision in self.decisions:
      if not decision.get("result"):
        self.decision = False
        break
      pass
    return

  # This may be too invasive...
  def update_decision( self, keys: dict, updates: dict, overall_changed: Callable = None):
    """updating decision of component. 
keys dict : descriptor of component. (eg: { "component": "ethernet", "device": "eth0" })
updates dict : values to update (eg: { "verdict": True, "message": "Network is working" })
overall_changed:

When a status/decision of component changes, this is called to update the decision of component which may or may not change the overall decision as well.

Since there is no way to listen to audio, only way to confirm the functionality of component is to listen to the sound played on the computer.
A triaging person can decide whether not sound playing. Also, if you plug in Ethernet to a router, the network status changes (such as detecting carrier) so it's done through this.
"""

    for decision in self.decisions:
      matched_decision = decision

      # Find a triage decision that matches all of criteria
      for key, value in keys.items():
        if decision.get(key) != value:
          matched_decision = None
          break
        pass
      
      # If found, end the search
      if matched_decision:
        break
      pass

    if matched_decision:
      tlog.debug( "Updating %s with %s" % (matched_decision["component"], str(updates)))
      for key, value in updates.items():
        if key == 'message':
          matched_decision[key] = value.strip() + " " + matched_decision[key].strip()
        elif key == 'result':
          # this should be bool value
          matched_decision[key] = value
        elif isinstance(value, str):
          matched_decision[key] = value.strip()
        else:
          # ???
          tlog.debug(f"??? {key} : {value}")
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
