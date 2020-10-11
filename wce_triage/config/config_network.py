#!/usr/bin/env python3
#

from .config_db import config_base, triage_config

class network_config(config_base):
  def __init__(self):
    super().__init__(triage_config, "network")
    pass

  @property.getter
  def ip_address(self):
    return self.get("ip_address")

  @property.setter
  def ip_address(self, value):
    return self.set("ip_address", value)
  
  @property.getter
  def bonded_interfaces(self):
    return self.get("bonded_interfaces")

  @property.setter
  def bonded_interfaces(self, value):
    return self.set("bonded_interfaces", value)


  def provision(self):
    pass
  


