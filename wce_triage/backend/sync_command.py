from .models import Model, ModelDispatch
from .process_runner import SimpleProcessRunner
from http import HTTPStatus

#
#
#
class SyncCommandRunner(SimpleProcessRunner):
  @classmethod
  def class_name(cls):
    return "sync"
  
  def __init__(self, dispatch: ModelDispatch):
    super().__init__(stdout_dispatch=dispatch, meta = {"tag": "syncing"})
    pass

  def queue_sync(self, image_files: list, target_disks: str, clean=False):

    if len(target_disks) == 0:
      self.tlog.debug("SYNC: Sync target disk is none.")
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
