import sys
from typing import Optional

from ..models import ModelDispatch
from ..internal.process_runner import SimpleProcessRunner, JsonOutputDispatch
from ..server import server


global optical_dispatch

class OpticalDriveTestRunner(SimpleProcessRunner):
  @classmethod
  def class_name(cls):
    return "opticaldrive"

  def __init__(self,
               stdout_dispatch: Optional[ModelDispatch] = None,
               stderr_dispatch: Optional[ModelDispatch] = None,
               meta=None):
    if meta is None:
      meta = {"tag": "opticaldrive"}
      pass
    super().__init__(stdout_dispatch=stdout_dispatch, stderr_dispatch=stderr_dispatch, meta=meta)
    pass

  def queue_test(self, device_name):
    args = [sys.executable, '-m', 'wce_triage.bin.test_optical', device_name]
    self.queue(args, {"args": args, "devnames": device_name})
    return
  pass

class OpticalDispatch(JsonOutputDispatch):

  """Network status"""
  def dispatch(self, update):
    super().dispatch(update)

    message = self.model.data["message"]
    server.update_component_decision({"component": "Optical drive", "device": message['device']},
                                     {"result": message['result'], "message": message['runMessage'],"verdict": message['verdict']})
    pass
  pass
