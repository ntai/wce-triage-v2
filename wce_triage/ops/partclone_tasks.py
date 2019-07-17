#
# Partclone tasks
#
# The heavy lifting is done by the image_volume and restore_volume in wce_triage.bin.
#

import datetime, re, subprocess, abc, os, select, time, uuid
from wce_triage.components.disk import Disk, Partition
from wce_triage.ops.tasks import *
from wce_triage.lib.timeutil import *
import functools
from .estimate import *
from wce_triage.lib.util import *
from wce_triage.lib.disk_images import *
tlog = get_triage_logger()

#
# Running partclone base class
#
class task_partclone(op_task_process):
  t0 = datetime.datetime.strptime('00:00:00', '%H:%M:%S')

  # This needs to match with process driver's output format.
  progress_re = re.compile(r'^\w+: partclone\.stderr:Elapsed: (\d\d:\d\d:\d\d), Remaining: (\d\d:\d\d:\d\d), Completed:\s+(\d+.\d*)%,\s+[^\/]+/min,')
  output_re = re.compile(r'^\w+: partclone\.stderr:(.*)')
  error_re = re.compile(r'^(\w+\.ERROR): (.*)')

  def __init__(self, description, **kwargs):
    # 
    super().__init__(description, **kwargs)

    self.start_re = []
    # If we don't skip the superblock part, the progress is totally messed up
    self.start_re.append(re.compile(r'File system:\s+EXTFS'))

    # 15 - fudge - partclone needs "disk sync" time
    self.fudge = kwargs.get('fudge', 15)
    pass

  def poll(self):
    super().poll()
    self.parse_partclone_progress()
    pass

  def parse_partclone_progress(self):
    #
    # Check the progress. driver prints everything to stderr
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

      # Look for the EXT parition cloning start marker
      while len(self.start_re) > 0:
        m = self.start_re[0].search(line)
        if not m:
          break
        self.start_re = self.start_re[1:]
        if len(self.start_re) == 0:
          self.set_progress(5, "Start imaging")
          self.imaging_start_seconds = in_seconds(current_time - self.start_time)
          pass
        pass

      # passed the start marker

      if len(self.start_re) == 0:
        m = self.progress_re.search(line)
        if m:
          elapsed = m.group(1)
          remaining = m.group(2)
          completed = float(m.group(3))

          dt_elapsed = datetime.datetime.strptime(elapsed, '%H:%M:%S') - self.t0
          dt_remaining = datetime.datetime.strptime(remaining, '%H:%M:%S') - self.t0

          self.set_time_estimate(self.imaging_start_seconds + in_seconds(dt_elapsed) + in_seconds(dt_remaining) + self.fudge)
          # Unfortunately, "completed" from partclone for usb stick is totally bogus.
          dt = current_time - self.start_time
          self.set_progress(self._estimate_progress_from_time_estimate(dt.total_seconds()), "elapsed: %s remaining: %s" % (elapsed, remaining))
          pass
        else:
          m = self.output_re.match(line)
          if m:
            self.message = m.group(1)
            pass

          m = self.error_re.match(line)
          if m:
            self.verdict.append(m.group(2))
            pass
          pass
        pass
      pass
    pass
  pass

#
#
#
class task_create_disk_image(task_partclone):
  
  def __init__(self, description, disk=None, partition_id="Linux", imagename=None, partition_size=None, **kwargs):
    super().__init__(description, time_estimate=disk.get_byte_size() / 500000000, **kwargs)
    self.disk = disk
    self.partition_id = partition_id
    self.imagename = imagename
    self.partition_size = partition_size
    pass

  # 
  def setup(self):
    part = self.disk.find_partition(self.partition_id)
    if part is None:
      self.set_progress(999, "No partion %s" % self.partition_id)
      return
    #
    if part.file_system is None:
      self.set_progress(999, "Partion %s exists but the file system is not fetched." % str(self.partition_id))
      return

    # Unlike others, image_volume outputs progress to stderr.
    self.argv = ["python3", "-m", "wce_triage.bin.image_volume", part.device_name, part.file_system, self.imagename ]
    super().setup()
    pass

  def explain(self):
    return "Create disk image of %s to %s using WCE Triage's image_volume" % (self.disk.device_name, self.imagename)
  pass

#
#
class task_restore_disk_image(task_partclone):
  
  # Restore partclone image file to the first partition
  def __init__(self, description, disk=None, partition_id="Linux", source=None, source_size=None, **kwargs):
    #
    super().__init__(description, time_estimate=source_size / 3000000, **kwargs)
    self.disk = disk
    self.partition_id = partition_id
    self.source = source
    self.source_size = source_size
    if self.source is None:
      raise Exception("bone head. it needs the source image.")
    pass

  def setup(self):
    part = self.disk.find_partition(self.partition_id)
    if part is None:
      raise Exception("Partition %s is not found." % self.partition_id)
    self.argv = ["python3", "-m", "wce_triage.bin.restore_volume", self.source, get_file_system_from_source(self.source), part.device_name]
    super().setup()
    pass

  def explain(self):
    return "Restore disk image from %s to %s %s" % (self.source, self.disk.device_name, str(self.partition_id))

  # ignore parsing partclone progress. for restore, it is 100$ wrong.
  def parse_partclone_progress(self):
    #
    # Check the progress. driver prints everything to stderr
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

      tlog.debug("partclone: %s" % line)
      # Look for the EXT parition cloning start marker
      while len(self.start_re) > 0:
        m = self.start_re[0].search(line)
        if not m:
          break
        self.start_re = self.start_re[1:]
        if len(self.start_re) == 0:
          self.set_progress(5, "Start imaging")
          self.imaging_start_seconds = in_seconds(current_time - self.start_time)
          pass
        pass

      # passed the start marker
      if len(self.start_re) == 0:
        m = self.progress_re.search(line)
        if m:
          self.log(line.strip())
          pass
        else:
          m = self.output_re.match(line)
          if m:
            msg = m.group(1).strip()
            if msg:
              self.log(msg)
              pass
            pass

          m = self.error_re.match(line)
          if m:
            self.verdict.append(m.group(2).strip())
            pass
          pass
        pass
      pass
    pass

  pass
