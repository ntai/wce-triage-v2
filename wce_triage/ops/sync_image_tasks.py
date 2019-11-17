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


class task_image_sync:
  """image sync task
"""
  def __init__(self, desc, **kwargs):
    self.partitions = []
    pass

  def add_mount_point(self, disk, part):
    self.partitions.append((disk, part))
    pass

  pass


class task_image_sync_delete( op_task_process_simple, task_image_sync ):
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
    task_image_sync.__init__(self, description)
    pass

  def setup(self):
    # First, need the list of files
    dirs = [ os.path.join(part.get_mount_point(), "usr", "local", "share", "wce", "wce-disk-images") for disk, part in self.partitions ]
    images = []
    for dir in dirs:
      try:
        images = images + list_image_files([dir])
      except FileNotFoundError:
        os.mkdir(dir)
        tlog.info("directory %s created" % dir)
        pass
      except Exception as exc:
        pass
      pass

    tlog.debug(str(self.argv))
    tlog.debug("---------- dirs")
    tlog.debug(dirs)
    tlog.debug("---------- images")
    tlog.debug(images)

    do_rm = False
    for fname, subdir, fullpath in images:
      if fname in self.keepers:
        tlog.debug("%s is in keepers. Skipping" % fname)
        continue
      if fname not in images:
        if os.path.exists(fullpath):
          tlog.debug("'%s' exists. adding to the argv" % fullpath)
          self.argv.append(fullpath)
          do_rm = True
          pass
        else:
          tlog.debug("'%s' does not exists." % fullpath)
          pass
        pass
      pass
    
    if not do_rm:
      self.argv = ["true"]
      pass

    super().setup()
    pass
  pass


class task_image_sync_copy(op_task_process_simple, task_image_sync):
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
    argv = bin + ['-m', 'wce_triage.bin.fanout_copy', self.source["fullpath"]]
    super().__init__(description,
                     argv=argv,
                     progress_finished="Image file %s copied" % source_filename,
                     time_estimate=100,
                     **kwargs)
    task_image_sync.__init__(self, description)
    pass

  def setup(self):
    # First, need the list of files
    #
    src_fname = self.source["name"]
    for disk, part in self.partitions:
      do_copy = True
      dir = os.path.join(part.get_mount_point(), "usr", "local", "share", "wce", "wce-disk-images")
      images = list_image_files([dir])
      for fname, subdir, fullpath in images:
        if fname == src_fname:
          do_copy = False
          tlog.debug("Destination has %s already." % fname)
          break
        pass
      if do_copy:
        self.argv.append("%s:%s" % (disk.device_name, os.path.join(dir, self.source["restoreType"], src_fname)))
        pass
      pass
    super().setup()
    pass

  def poll(self):
    super().poll()
    self.parse_fanout_copy_progess()
    pass

  def parse_fanout_copy_progess(self):
    #
    if len(self.err) == 0:
      return

    # look for a line
    while True:
      newline = self.err.find('\n')
      if newline < 0:
        break
      line = self.err[:newline]
      self.err = self.err[newline+1:]
      current_time = datetime.datetime.now()

      # each line is a json record
      report = json.loads(line)
      event = report['event']
      message = report['message']
      self.set_progress(message['progress'], message['runMessage'])
      self.set_time_estimate(message['runEstimate'])
      pass
    pass

  pass


class task_image_sync_metadata(op_task_process_simple, task_image_sync):
  """sync metadata
"""
  def __init__(self, description, disk=None, testflight=False, **kwargs):
    self.disk = disk
    self.testflight = testflight
    argv= ["rsync"]

    super().__init__(description,
                     argv=argv,
                     time_estimate=2,
                     progress_finished="Disk metadata synced for %s" % disk.device_name,
                     **kwargs)
    task_image_sync.__init__(self, description)
    pass

  def setup(self):
    src_metadata_dir = os.path.join("/", "usr", "local", "share", "wce", "wce-disk-images") + "/"
    dst_metadata_dir = None

    flag = "-n" if self.testflight else "-q"

    for disk, part in self.partitions:
      if disk is not self.disk:
        continue
      dst_metadata_dir = os.path.join(part.get_mount_point(), "usr", "local", "share", "wce", "wce-disk-images") + "/"
      break

    if dst_metadata_dir:
      self.argv = ["rsync", flag, "-a", "-f", "+ */.*", "-f", "- /*/[[:alnum:]]*", src_metadata_dir, dst_metadata_dir]
    else:
      raise Exception("Bug")

    super().setup()
    pass

  pass
