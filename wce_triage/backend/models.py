from .view import View
from typing import Optional
import threading


class Model(object):
  _model: dict
  _meta: dict
  model_state: Optional[bool]
  cumulative: bool
  key: str
  lock: threading.Lock

  def __init__(self, cumulative=False, key="message", meta=None, default=None):
    self.lock = threading.Lock()
    self._meta = {} if meta is None else meta
    self.key = key
    self.cumulative = cumulative
    self.model_state = None
    self.clear(default=default)
    pass

  def set_model_data(self, data):
    self.lock.acquire()
    try:
      self.model_state = True
      if self.cumulative:
        self._model[self.key].append(data)
      else:
        self._model = data
        pass
      pass
    finally:
      self.lock.release()
      pass
    pass

  def clear(self, default=None):
    self.lock.acquire()
    try:
      self.model_state = None
      if default:
        self._model = {self.key: [default]} if self.cumulative else default
      else:
        self._model = {self.key: []} if self.cumulative else {}
        pass
      pass
    finally:
      self.lock.release()
      pass
    pass

  @property
  def data(self):
    return self._model

  @property
  def meta(self):
    return self._meta

  def set_model_state(self, state: bool):
    self.model_state = state
    pass

  def close(self):
    """signal to no more set_model_data incoming."""
    pass
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

  def start(self, tag, args):
    pass

  def dispatch(self, update):
    """dispatches an update to the view and model.
    :param update:
    :return: update
    """
    if self.view:
      self.view.updating(self.model.data, update, self.model.meta)
      pass
    self.update_model_data(update)
    if self.view:
      # Give view a chance to see both old and new model data
      self.view.updated(self.model.data, self.model.meta)
      pass
    return update

  def update_model_data(self, update):
    """update the model data.
    may override
    """
    self.model.set_model_data(update)
    return update

  def end(self, tag, args):
    pass

