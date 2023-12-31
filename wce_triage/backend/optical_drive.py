import sys
from typing import Optional

from .models import Model, ModelDispatch
from .process_runner import SimpleProcessRunner, JsonOutputDispatch
from ..components import detect_optical_drives
from ..lib import get_triage_logger
from .server import server
from http import HTTPStatus


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

def route_opticaldrivetest():
  """Test optical drive"""
  global optical_dispatch

  opticals = server.opticals
  if opticals.count() == 0:
    od = detect_optical_drives()
    if len(od) == 0:
      return {}, HTTPStatus.NOT_FOUND
    else:
      server.update_triage()
      opticals = server.opticals
      pass

  tlog = get_triage_logger()
  runner = server.get_runner(runner_class=OpticalDriveTestRunner, create=False)
  if runner is None:
    optical_dispatch = OpticalDispatch(Model())
    runner = OpticalDriveTestRunner(optical_dispatch)
    server.register_runner(runner)
    runner.start()
    pass

  # Since reading optical is slow, the answer goes back over websocket.
  for optical in opticals.drives:
    tlog.debug("run wce_triage.bin.test_optical " + optical.device_name)
    runner.queue_test(optical.device_name)
    pass
  # This is meaningless.
  return {}
