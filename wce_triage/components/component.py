
import abc

class Component(object):

  # String to ID the component type (eg. CPU, Memory, Disk...)
  @abc.abstractmethod
  def get_component_type(self):
    return None


  # This can produce multiple entries so it must return as list
  @abc.abstractmethod
  def decision(self):
    pass

  # detect changes return a list of tuples with two elements.
  # first element is the update key, and 2nd is the value to update
  def detect_changes(self):
    return []

  pass

