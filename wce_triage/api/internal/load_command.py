import sys
from typing import Optional
from fastapi import status

from .. import op_load
from ..messages import UserMessages
from ..models import ModelDispatch
from ..internal.process_runner import SimpleProcessRunner
from ...lib.disk_images import read_disk_image_types
from ...lib import get_triage_logger
from ..server import server
from ..operations import WIPE_TYPES

#
#
#
class LoadCommandRunner(SimpleProcessRunner):

  # Since ProcessRunner is generic, there is not much reason to make this "Load" only but by limiting one thread
  # to run particular command, it's serializied.

  @classmethod
  def class_name(cls):
    return op_load

  def __init__(self,
               stdout_dispatch: Optional[ModelDispatch] = None,
               stderr_dispatch: Optional[ModelDispatch] = None,
               meta=None):
    if meta is None:
      meta = {"tag": "loadimage"}
      pass
    super().__init__(stdout_dispatch=stdout_dispatch,
                     stderr_dispatch=stderr_dispatch,
                     meta=meta)
    pass

  def queue_load(self, devname: str, load_type: str, imagefile: str, image_size: str | None, wipe_request: str, newhostname: str) -> None:
    args = [sys.executable, '-m', 'wce_triage.ops.restore_image_runner', devname, imagefile, image_size, load_type]
    tlog = get_triage_logger()

    if newhostname and len(newhostname) > 1:
      args.append('-m')
      args.append(newhostname)
      pass

    wipe = None
    for wipe_type in WIPE_TYPES:
      if wipe_type.get("id") == wipe_request:
        wipe_option = wipe_type.get("arg")
        if wipe_option:
          args.append(wipe_option)
          pass
        break
      pass

    target = None
    for disk in server.disk_portal.disks:
      if disk.device_name == devname:
        target = disk
        break
      pass

    if target is None:
      message = "No such disk " + devname
      tlog.info(message)
      return {"message": message}, status.HTTP_400_BAD_REQUEST

    #disk = server.disk_portal.find_disk_by_device_name(devname)

    # loadType is a single word coming back from read_disk_image_types()
    image_type = None
    for _type in read_disk_image_types():
      if _type["id"] == load_type:
        image_type = _type
        break
      pass

    if image_type is None:
      message = "Image type %s is not known." % load_type
      UserMessages.error(message)
      return {"message": message}, status.HTTP_400_BAD_REQUEST

    destdir = image_type.get('catalogDirectory')
    if destdir is None:
      msg = UserMessages.error("Imaging type info %s does not include the catalog directory." % image_type.get("id"))
      return {"message": msg}, status.HTTP_400_BAD_REQUEST

    # Load image runs its own course, and output will be monitored by a call back
    self.queue(args, {"args": args, "devname": devname, "imagefile": imagefile, "wipe": wipe, "newhostname": newhostname })
    return {}, status.HTTP_200_OK

  pass


