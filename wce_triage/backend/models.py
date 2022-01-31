from wce_triage.components.disk import DiskPortal
from .view import View
from typing import Optional

class Model(object):
  _model: dict
  model_state: Optional[bool]

  def __init__(self):
    self._model = {}
    self.model_state = None
    pass

  def set_model_data(self, updates):
    self._model = updates
    pass

  @property
  def data(self):
    return self._model
  pass


class ModelDispatch(object):
  """Dispatch connects the mode and view, and dispatches the model update"""
  view: Optional[View]
  model: Model

  def __init__(self, model, view=None):
    self.model = model
    self.view = view
    pass

  def set_view(self, view):
    self.view = view
    pass

  def start(self):
    pass

  def dispatch(self, update):
    if self.view:
      self.view.updating(self.model.data, update)
      pass
    self.update_model_data(update)
    if self.view:
      # Give view a chance to see both old and new model data
      self.view.updated(self.model.data)
      pass
    pass

  def update_model_data(self, update):
    self.model.set_model_data(update)
    pass

  def end(self):
    pass

#
# messages is like a logging but it's for the user from the triage.
#

class StringsModel(Model):
  def __init__(self):
    super().__init__()
    self._model = {"lines": []}
    pass

  def append_line(self, message):
    self._model["lines"].append(message)
    pass


class StringsDispatch(ModelDispatch):

  def __init__(self, model: StringsModel, view=None):
    super().__init__(model=model, view=view)
    self.model_state = False # Model state is never done for the message, and the initial state not None either.
    pass

  def update_model_data(self, update):
    self.model.append_line(update)
    pass


class DiskModel(Model):
  disk_portal: DiskPortal

  def __init__(self):
    super().__init__()
    self.disk_portal = DiskPortal()
    pass

  def refresh_disks(self):
    self.set_model_data(self.disk_portal.decision())
    pass

  pass
