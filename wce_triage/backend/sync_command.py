from typing import Optional

from .models import ModelDispatch
from .process_runner import SimpleProcessRunner
from http import HTTPStatus

from ..lib import get_triage_logger


#
#
#
class SyncCommandRunner(SimpleProcessRunner):
  @classmethod
  def class_name(cls):
    return "sync"
  
  def __init__(self,
               stdout_dispatch: Optional[ModelDispatch] = None,
               stderr_dispatch: Optional[ModelDispatch] = None,
               meta=None):
    if not meta:
      meta = {"tag": "syncing"}
    super().__init__(stdout_dispatch=stdout_dispatch, stderr_dispatch=stderr_dispatch, meta=meta)
    pass

  def queue_sync(self, image_files: list, target_disks: str, clean=False):
    tlog = get_triage_logger()
    if len(target_disks) == 0:
      tlog.debug("SYNC: Sync target disk is none.")
      return {}, HTTPStatus.OK

    if clean:
      # clean
      args = ['python3', '-m', 'wce_triage.ops.sync_image_runner', ",".join(target_disks)] + ["clean"]
    else:
      args = ['python3', '-m', 'wce_triage.ops.sync_image_runner', ",".join(target_disks)] + image_files
      pass
    self.queue(args, {"args": args})
    return {}, HTTPStatus.OK

  pass
