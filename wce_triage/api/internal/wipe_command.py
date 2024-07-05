import sys
import typing

from fastapi import status
from .. import op_wipe
from ..models import ModelDispatch
from ..internal.process_runner import SimpleProcessRunner

#
#
#
class WipeCommandRunner(SimpleProcessRunner):

  # Since ProcessRunner is generic, there is not much reason to make this "Wipe" only but by limiting one thread
  # to run particular command, it's serializied.

  @classmethod
  def class_name(cls):
    return op_wipe

  def __init__(self, stdout_dispatch: ModelDispatch = None, stderr_dispatch: ModelDispatch = None, meta=None):
    if not meta:
      meta = {"tag": "zerowipe"}
    super().__init__(stdout_dispatch=stdout_dispatch, stderr_dispatch=stderr_dispatch, meta=meta)
    pass

  def queue_wipe(self, devices: typing.List[str]):
    args = [sys.executable, '-m', 'wce_triage.bin.multiwipe'] + devices
    self.queue(args, {"args": args, "devnames": ",".join(devices)})
    return {}, status.HTTP_200_OK

  pass
