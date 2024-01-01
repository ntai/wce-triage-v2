import sys
from .models import ModelDispatch
from .process_runner import SimpleProcessRunner
from http import HTTPStatus

#
#
#
class WipeCommandRunner(SimpleProcessRunner):

  # Since ProcessRunner is generic, there is not much reason to make this "Wipe" only but by limiting one thread
  # to run particular command, it's serializied.

  @classmethod
  def class_name(cls):
    return "wipe"

  def __init__(self, stdout_dispatch: ModelDispatch = None, stderr_dispatch: ModelDispatch = None, meta=None):
    if not meta:
      meta = {"tag": "zerowipe"}
    super().__init__(stdout_dispatch=stdout_dispatch, stderr_dispatch=stderr_dispatch, meta=meta)
    pass

  def queue_wipe(self, devices):
    args = [sys.executable, '-m', 'wce_triage.bin.multiwipe'] + devices
    self.queue(args, {"args": args, "devnames": ",".join(devices)})
    return {}, HTTPStatus.OK

  pass
