import sys
import typing
from typing import Optional
from http import HTTPStatus

from .. import op_save
from ..messages import UserMessages
from ..models import ModelDispatch
from ..internal.process_runner import SimpleProcessRunner
from ...lib.disk_images import read_disk_image_types
from ...lib import get_triage_logger
from ...components.disk import PartitionLister
from ..server import server


#
#
#
class SaveCommandRunner(SimpleProcessRunner):

  @classmethod
  def class_name(cls):
    return op_save

  def __init__(self,
               stdout_dispatch: Optional[ModelDispatch] = None,
               stderr_dispatch: Optional[ModelDispatch] = None,
               meta=None):
    meta = {"tag": "saveimage"}
    super().__init__(stdout_dispatch=stdout_dispatch, stderr_dispatch=stderr_dispatch, meta=meta)
    pass

  def queue_save(self, devname: str, saveType: str, destdir: str, partid: str) -> typing.Tuple[dict, HTTPStatus]:
    tlog = get_triage_logger()
    target = None
    for disk in server.disk_portal.disks:
      if disk.device_name == devname:
        target = disk
        break
      pass

    if target is None:
      tlog.info("No such disk " + devname)
      return {}, HTTPStatus.BAD_REQUEST

    disk = server.disk_portal.find_disk_by_device_name(devname)
    lister = PartitionLister(disk)
    lister.execute()

    part = disk.find_partition(partid)
    if part is None:
      part = disk.find_partition_by_file_system('ext4')

      if part is None:
        for partition in disk.partitions:
          tlog.debug(str(partition))
          pass
        UserMessages.error("Device %s has no EXT4 partition for imaging." % disk.device_name)
        return {}, HTTPStatus.BAD_REQUEST

    partition_id = disk.get_partition_id(part)
    if partition_id is None:
      UserMessages.error("Partition %s has not valid ID." % part.device_name)
      return {}, HTTPStatus.BAD_REQUEST

    # saveType is a single word coming back from read_disk_image_types()
    image_type = None
    for _type in read_disk_image_types():
      if _type["id"] == saveType:
        image_type = _type
        break
      pass

    if image_type is None:
      UserMessages.error("Image type %s is not known." % saveType)
      return {}, HTTPStatus.BAD_REQUEST

    destdir = image_type.get('catalogDirectory')
    if destdir is None:
      msg = UserMessages.error("Imaging type info %s does not include the catalog directory." % image_type.get("id"))
      return {"message": msg}, HTTPStatus.BAD_REQUEST

    # save image runs its own course, and output will be monitored by a call back
    args = [sys.executable, '-m', 'wce_triage.ops.create_image_runner', devname, str(partition_id), destdir]
    self.queue(args, {"args": args, "devname": devname, "destdir": destdir, "partid": str(partition_id)})
    return {}, HTTPStatus.OK

  pass
