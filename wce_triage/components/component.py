# Copyright (c) 2019-2023 Naoyuki tai
# MIT license - see LICENSE
"""# Component base class for computer components.

## Subclass must implement following member functions.

get_component_type(self) -> str
  The component type name, and must be reasonable string to be displayed for user.
  Something like "CPU", "Memory". 

decision(self) -> list
  Returns a list of triage result which is a dcit. Component may one or more triage result.
  For example, "Disk" component may return the result for each disk as well as overall triage result.


## Subclass may override following

detect_changes(self) -> list
  

"""

import abc
from typing import List

class Component(object):
  """Component base class for computer.

Component here is a piece of hardware on computer that we care to know.
For example, CPU is a component. 
"""

  # String to ID the component type (eg. CPU, Memory, Disk...)
  @abc.abstractmethod
  def get_component_type(self) -> str:
    """returns a generic component name.

This is presented to human as a name for this particular component (like "CPU") 
as well as this is an ID.  (It's not very i18n friendly...)
"""
    return None


  # This can produce multiple entries so it must return as list
  @abc.abstractmethod
  def decision(self, **kwargs) -> list:
    """deciding the triage result.

After gathering info of component, decision function returns a list of dict objects.
The dictionary contains following items:
  "component": self.get_component_type()
  "result":  boolean value of pass or fail.
  "message": brief message about the reason for the decision.

A component can return more than one decisions. For example, if you have a 
multiple video cards, the component type returns every video card found.
"""

  # detect changes return a list of dict objects.
  def detect_changes(self) -> List[tuple]:
    '''detect changes return a list of dict objects.

A dictionary as elemet of list is as follows:
  "component": component type
  "device": device name
  "device_type": device type
  "result": good or bad in boolean

For now, only component that can change the state is network device.
For example, ethernet cable plugging in can produce the change.
'''
    return []

  pass

