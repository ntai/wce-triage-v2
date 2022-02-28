from .messages import UserMessages
from .models import Model, ModelDispatch
from .process_runner import SimpleProcessRunner
from ..lib.disk_images import read_disk_image_types
from ..lib.util import get_triage_logger
from ..components.disk import PartitionLister
from .server import server
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

  def __init__(self, dispatch: ModelDispatch):
    super().__init__(stdout_dispatch=dispatch, meta = {"tag": "wipe"})
    pass

  def queue_wipe(self, devices):
    args = ['python3', '-m', 'wce_triage.bin.multiwipe'] + devices
    self.queue(args, {"args": args, "devnames": ",".devices})
    return {}, HTTPStatus.OK

  pass
