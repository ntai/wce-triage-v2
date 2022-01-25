from wce_triage.components.disk import DiskPortal
from .view import View
from typing import Optional

class Model(object):
  _model: dict
  model_state: Optional[bool]
  view: Optional[View]
  

  def __init__(self):
    self._model = {}
    self.model_state = None
    self.view = None
    pass


  def set_view(self, view):
    self.view = view
    pass

  
  def set_model_data(self, updates):
    if self.view:
      self.view.update(self._model, updates)
    self._model = updates
    pass

  @property
  def data(self):
    return self._model
  
  pass


class DiskModel(Model):
  disk_portal: DiskPortal

  def __init__(self):
    super().__init__()
    self.disk_portal = {}
    pass

  def refresh_disks(self):
    self.set_model_data(DiskPortal())

  pass


