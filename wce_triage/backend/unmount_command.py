from .models import ModelDispatch
from .process_runner import SimpleProcessRunner
from http import HTTPStatus
from ..components.disk import PartitionLister, Disk


#
#
#
class UnmountCommandRunner(SimpleProcessRunner):

  @classmethod
  def class_name(cls):
    return "unmount"

  def __init__(self, dispatch: ModelDispatch):
    super().__init__(stdout_dispatch=dispatch, meta = {"tag": "unmount"})
    pass

  def queue_unmount(self, devices):
    parts = [PartitionLister(Disk(device_name=device)).execute() for device in devices]
    part : PartitionLister
    for part in parts:
      part_names = [partition.partition_name for partition in part.disk.partitions]
      args = ['umount'] + part_names
      self.queue(args, {"args": args, "devnames": ",".join(part_names)})
      pass
    return {}, HTTPStatus.OK

  pass
