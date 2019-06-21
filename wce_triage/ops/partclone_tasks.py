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

#
# Running partclone base class
#
class task_partclone(op_task_process):
  t0 = datetime.datetime.strptime('00:00:00', '%H:%M:%S')

  # This needs to match with process driver's output format.
  progress_re = re.compile(r'^partclone\.stderr:Elapsed: (\d\d:\d\d:\d\d), Remaining: (\d\d:\d\d:\d\d), Completed:\s+(\d+.\d*)%,\s+[^\/]+/min,')

  def __init__(self, description, **kwargs):
    # 
    super().__init__(description, **kwargs)

    self.start_re = []
    # If we don't skip the superblock part, the progress is totally messed up
    self.start_re.append(re.compile(r'Reading Super Block')) # This is for reading superblock.
    self.start_re.append(re.compile(r'done')) # This is for reading superblock.
    self.start_re.append(re.compile(r'File system:\s+EXTFS'))
    pass

  def poll(self):
    super().poll()
    self.parse_partclone_progress()
    pass

  def parse_partclone_progress(self):
    #
    # Check the progress. driver prints everything to stdout
    #
    if len(self.out) == 0:
      return
    
    # look for a line
    while True:
      newline = self.out.find('\n')
      if newline < 0:
        break
      line = self.out[:newline]
      self.out = self.out[newline+1:]
        
      # Look for the EXT parition cloning start marker
      while len(self.start_re) > 0:
        m = self.start_re[0].search(line)
        if not m:
          break
        self.start_re = self.start_re[1:]
        if len(self.start_re) == 0:
          self.set_progress(5, "Start imaging")
          self.imaging_start_seconds = in_seconds(datetime.datetime.now() - self.start_time)
          pass
        pass

      # passed the start marke
      if len(self.start_re) == 0:
        m = self.progress_re.search(line)
        if m:
          elapsed = m.group(1)
          remaining = m.group(2)
          completed = float(m.group(3))

          dt_elapsed = datetime.datetime.strptime(elapsed, '%H:%M:%S') - self.t0
          dt_remaining = datetime.datetime.strptime(remaining, '%H:%M:%S') - self.t0

          # 10 is fudge - and partclone actually needs "disk sync" time
          self.set_time_estimate(self.imaging_start_seconds + in_seconds(dt_elapsed) + in_seconds(dt_remaining) + 10)
          self.set_progress(round(completed*0.95)+4, "elapsed: %s remaining: %s" % (elapsed, remaining))
          pass
        pass
      pass
    pass
  pass

#
#
#
class task_create_disk_image(task_partclone):
  
  def __init__(self, description, disk=None, partition_id="Linux", imagename=None):
    super().__init__(description, time_estimate=disk.get_byte_size() / 500000000)
    self.disk = disk
    self.partition_id = partition_id
    self.imagename = imagename
    pass

  # 
  def setup(self):
    part = self.disk.find_partition(self.partition_id)
    if part is None:
      self.set_progress(999, "No partion %s" % self.partition_id)
      return
    self.argv = ["python3", "-m", "wce_triage.bin.image_volume", part.device_name, self.imagename ]
    super().setup()
    pass

  def explain(self):
    return "Create disk image of %s using WCE Triage's image_volume" % self.disk.device_name

  pass

#
#
class task_restore_disk_image(task_partclone):
  
  # Restore partclone image file to the first partition
  def __init__(self, description, disk=None, partition_id="Linux", source=None):
    super().__init__(description, time_estimate=disk.get_byte_size() / 500000000)
    self.disk = disk
    self.partition_id = partition_id
    self.source = source
    if self.source is None:
      raise Exception("bone head. it needs the source image.")
    pass

  def setup(self):
    part = self.disk.find_partition(self.partition_id)
    self.argv = ["python3", "-m", "wce_triage.bin.restore_volume", part.device_name, self.source ]
    super().setup()
    pass

  def explain(self):
    return "Restore disk image from %s to %s using WCE Triage's restore_volume" % (self.source, self.disk.device_name)

  pass
