#
# Tasks: each task is a operation. Some tasks can take a long time.
#
# For example, a task is like mkfs. As the task runs, it should produce progress
#
# By calling into diskop, it creates the plan - which is the sequence of tasks.
# exec runs through the tasks.
#

import datetime, re, subprocess, abc, os, select, time, uuid, json, traceback, shutil
import struct
from ..components.disk import Disk, Partition, PartitionLister, canonicalize_file_system_name
from ..lib.util import get_triage_logger
from ..lib.timeutil import *
import uuid
from .run_state import *
from ..lib.disk_images import *


tlog = get_triage_logger()

from .tasks import *


class task_image_sync(op_task_process_simple):
  """image sync task
"""
  def __init__(self, desc, **kwargs):
    super().__init__(desc, **kwargs)
    self.partitions = []
    pass

  def add_mount_point(self, disk, part):
    self.partitions.append((disk, part))
    pass

  pass


class task_image_sync_delete( task_image_sync ):
  """delete disk image file
"""

  def __init__(self, description, keepers=[], testflight=False, **kwargs):
    if testflight:
      print("Test flight %s" % description)
      pass
    self.keepers = {}
    for keeper in keepers:
      self.keepers[keeper['name']] = keeper
      pass
    self.testflight = testflight
    if self.testflight:
      argv = ["echo", "rm"]
    else:
      argv = ["rm"]
      pass
    super().__init__(description,
                     argv=argv,
                     progress_finished="Images deleted",
                     time_estimate=5,
                     **kwargs)
    pass

  def setup(self):
    # First, need the list of files
    dirs = [ os.path.join(part.get_mount_point(), "usr", "local", "share", "wce", "wce-disk-images") for disk, part in self.partitions ]
    images = list_image_files(dirs)

    tlog.debug(str(self.argv))
    tlog.debug("---------- dirs")
    tlog.debug(dirs)
    tlog.debug("---------- images")
    tlog.debug(images)

    for fname, subdir, fullpath in images:
      if fname in self.keepers:
        tlog.debug("%s is in keepers. Skipping" % fname)
        continue
      if fname not in images:
        if os.path.exists(fullpath):
          tlog.debug("'%s' exists. adding to the argv" % fullpath)
          self.argv.append(fullpath)
          pass
        else:
          tlog.debug("'%s' does not exists." % fullpath)
          pass
        pass
      pass
    super().setup()
    pass
  pass


class task_image_sync_copy(task_image_sync):
  """copy disk image files
"""

  def __init__(self, description, source={}, testflight=False, **kwargs):
    self.source = source
    self.testflight = testflight
    if self.testflight:
      bin = ["echo", "python3"]
    else:
      bin = ["python3"]
      pass

    source_filename = self.source["name"]
    super().__init__(description,
                     argv= bin + ['-m', 'wce_triage.bin.fanout_copy', source_filename],
                     progress_finished="Image file %s copied" % source_filename,
                     time_estimate=100,
                     **kwargs)
    pass

  def setup(self):
    # First, need the list of files
    #
    source_filename = self.source["name"]
    for disk, part in self.partitions:
      dir = os.path.join(part.get_mount_point(), "usr", "local", "share", "wce", "wce-disk-images")
      images = list_image_files([dir])
      sync = True
      for fname, subdir, fullpath in images:
        if fname == source_filename:
          sync = False
          tlog.debug("Destination has %s already." % fname)
          break
        pass
      
      if sync:
        self.argv.append("%s:%s" % (disk.device_name, os.path.join(dir, subdir, source_filename)))
        pass
      pass
    super().setup()
    pass
  pass
