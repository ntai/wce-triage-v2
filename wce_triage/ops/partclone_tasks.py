#
# Partclone tasks
#
# The heavy lifting is done by the image_volume and restore_volume in wce_triage.bin.
#
"""tasks that deals with partclone command.
Actual running of process is done by wce_triage/bin's process driver and this one is like a shim between the process driver and the runner.
Important part is about parsing the partclone output and send out the progress.
"""

import datetime, re, subprocess, abc, os, select, time, uuid

from ..components.disk import Disk, Partition
from .tasks import *
from ..lib.timeutil import *
import functools
from .estimate import *
from ..lib.util import *
from ..lib.disk_images import *

tlog = get_triage_logger()

#
# Running partclone base class
#
class task_partclone(op_task_process):
  t0 = datetime.datetime.strptime('00:00:00', '%H:%M:%S')

  # This needs to match with process driver's output format.
  progress0_re = re.compile(r'partclone\.stderr:Elapsed: (\d\d:\d\d:\d\d), Remaining: (\d\d:\d\d:\d\d), Completed:\s+(\d+\.\d*)%,\s+[^\/]+/min,')
  progress1_re = re.compile(r'partclone\.stderr:current block:\s+(\d+), total block:\s+(\d+), Complete:\s+(\d+\.\d*)%')
  output_re = re.compile(r'^\w+: partclone\.stderr:(.*)')
  error_re = re.compile(r'^(\w+\.ERROR): (.*)')

  def __init__(self, description, **kwargs):
    #
    kwargs['progress_running'] = None
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
        m = self.progress0_re.search(line)
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
    # FIXME: This time_estimate is so wrong in so many levels.
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
    speed = disk.estimate_speed(operation="restore")
    self.initial_time_estimate=2*source_size/speed
    super().__init__(description, time_estimate=self.initial_time_estimate, **kwargs)
    self.disk = disk
    self.partition_id = partition_id
    self.source = source
    self.source_size = source_size
    if self.source is None:
      raise Exception("bone head. it needs the source image.")
    self.percent_done = None
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
    # Check the progress.
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
        m = self.progress1_re.search(line)
        if m:
          self.percent_done = m.group(1)
          dt = current_time - self.start_time
          # self.set_progress(self._estimate_progress_from_time_estimate(dt.total_seconds()), "elapsed: %s remaining: %s" % (elapsed, remaining))
          percent = self._estimate_progress_from_time_estimate(dt.total_seconds())
          try:
            percent = min(float(m.group(3)), 99)
            if percent > 10:
              sofar = percent/100
              # Progress coming back from partclone is always super optimistic
              # it doesn't include the cache flushing at the end. In other word, it
              # is reporting how much input it got, not how much it is written to the
              # destination.
              fudge = (1.05 + 0.1 * (1-sofar))
              # This will still overestimate a lot but probably okay
              new_estimate = sum([self.time_estimate, (in_seconds(dt) / sofar) * fudge, self.initial_time_estimate])/3
              self.set_time_estimate(new_estimate)
              percent = self._estimate_progress_from_time_estimate(dt.total_seconds())
              pass
            pass
          except:
            pass
          current_block = m.group(1)
          total_blocks = m.group(2)
          block_percent = round(float(current_block) / float(total_blocks) * 100.0, 1)
          self.set_progress(percent, "{progress}% done - {current} of {total} blocks completed.".format(progress=block_percent, current=current_block, total=total_blocks))
          pass

        m = self.progress0_re.search(line)
        if m:
          tlog.debug(line.strip())
          pass
        else:
          m = self.output_re.match(line)
          if m:
            msg = m.group(1).strip()
            if msg:
              tlog.debug(msg)
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
