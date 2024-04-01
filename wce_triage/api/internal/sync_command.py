import sys
import typing
from typing import Optional
from fastapi import status

from .. import op_sync
from ..models import ModelDispatch
from ..internal.process_runner import SimpleProcessRunner

from ...lib import get_triage_logger


#
#
#
class SyncCommandRunner(SimpleProcessRunner):
  @classmethod
  def class_name(cls):
    return op_sync
  
  def __init__(self,
               stdout_dispatch: Optional[ModelDispatch] = None,
               stderr_dispatch: Optional[ModelDispatch] = None,
               meta=None):
    if not meta:
      meta = {"tag": "syncing"}
    super().__init__(stdout_dispatch=stdout_dispatch, stderr_dispatch=stderr_dispatch, meta=meta)
    pass

  def queue_sync(self, image_files: list, target_disks: typing.List[str], clean=False):
    tlog = get_triage_logger()
    if len(target_disks) == 0:
      tlog.debug("SYNC: Sync target disk is none.")
      return {}, status.HTTP_400_BAD_REQUEST

    if clean:
      # clean
      args = [sys.executable, '-m', 'wce_triage.ops.sync_image_runner', ",".join(target_disks)] + ["clean"]
    else:
      args = [sys.executable, '-m', 'wce_triage.ops.sync_image_runner', ",".join(target_disks)] + image_files
      pass
    self.queue(args, {"args": args})
    return {}, status.HTTP_200_OK

  pass
