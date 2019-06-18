#
# Tasks: each task is a operation. Some tasks can take a long time.
#
# For example, a task is like mkfs. As the task runs, it should produce progress
#
# By calling into diskop, it creates the plan - which is the sequence of tasks.
# exec runs through the tasks.
#

import datetime, re, subprocess, abc, os, select, time, uuid
import components.pci
from components.disk import Disk, Partition
from ops.tasks import *
from lib.timeutil import *
import functools

#
# Running partclone base class
#
class task_partclone(op_task_process):
  t0= datetime.datetime.strptime('00:00:00', '%H:%M:%S')

  def __init__(self, description):
    self.time_estimates = []
    self.estimate_count = 0
    # 
    super().__init__(description, argv=None, time_estimate=600, encoding='iso-8859-1')

    self.start_re = []
    self.start_re.append(re.compile(r'Partclone [^ ]+ http://partclone.org\n'))
    self.start_re.append(re.compile(r'Starting to clone device \(/dev/\w+\) to image \([^\)]+\)\n'))
    self.start_re.append(re.compile(r'Reading Super Block\n'))
    self.start_re.append(re.compile(r'Calculating bitmap... Please wait... [^\n]+\n[^\n]+\n[^\n]+\n'))
    self.start_re.append(re.compile(r'File system:\s+EXTFS\n'))
    self.start_re.append(re.compile(r'Device size:\s+[\d.]+\s+GB\n'))
    self.start_re.append(re.compile(r'Space in use:\s+[\d.]+\s+GB\n'))
    self.start_re.append(re.compile(r'Free Space:\s+[\d.]+\s+MB\n'))
    self.start_re.append(re.compile(r'Block size:\s+\d+\s+Byte\n'))
    self.start_re.append(re.compile(r'Used block :\s+\d+\n'))
    
    self.progress_re = re.compile(r'\r\s+\rElapsed: (\d\d:\d\d:\d\d), Remaining: (\d\d:\d\d:\d\d), Completed:\s+(\d+.\d*)%,\s+([^\/]+)/min,')
    pass

  def parse_partclone_progress(self):
    #
    # Check the progress
    if len(self.err) > 0:
      while len(self.start_re) > 0:
        m = self.start_re[0].match(self.err)
        if not m:
          break
        self.start_re = self.start_re[1:]
        self.err = self.err[len(m.group(0)):]
        pass
      if len(self.start_re) == 0:
        self.set_progress(10, "Start imaging")
      else:
        while True:
          m = self.progress_re.search(self.err)
          if not m:
            break
          self.err = self.err[len(m.group(0)):]

          elapsed = m.group(1)
          remaining = m.group(2)
          completed = float(m.group(3))

          dt_elapsed = datetime.datetime.strptime(elapsed, '%H:%M:%S') - self.t0
          dt_remaining = datetime.datetime.strptime(remaining, '%H:%M:%S') - self.t0

          self.set_time_estimate(in_seconds(dt_elapsed) + in_seconds(dt_remaining))
          self.set_progress(round(completed*0.9)+10, "elapsed: %s remaining: %s" % (elapsed, remaining))
          pass
        pass
      pass
    pass

  def set_time_estimate(self, time_estimate):
    if len(self.time_estimates) == 0:
      self.time_estimates = [ time_estimate, time_estimate, time_estimate ]
      pass
    self.time_estimates[self.estimate_count] = time_estimate
    self.time_estimate = functools.reduce(lambda x,y : x+y, self.time_estimates) / len(self.time_estimates)
    self.estimate_count = (self.estimate_count + 1) % len(self.time_estimates)
    pass

  pass

#
#
#
class task_create_disk_image(task_partclone):
  
  def __init__(self, description, disk=None, partition_id="Linux", stem_name=None, compressor=["pigz"], destdir="/mnt/www/wce-disk-images"):
    super().__init__(description)
    self.stem_name = stem_name
    self.disk = disk
    self.partition_id = partition_id
    self.destdir = destdir

    self.compressor = compressor
    self.compressor_err = ""
    #
    self.imagename = os.path.join(self.destdir, "%s-%s.partclone.gz" % (self.stem_name, datetime.date.today().isoformat()))
    pass

  # Using partclone is different from other tasks.
  # stdout goes into compressor and the output of compressor goes out as binary file
  def setup(self):
    if not os.path.exists(self.destdir):
      self.set_progress(999, "Destination directory does not exist.")
      return

    # Final product
    self.outputfile = open(self.imagename, "wb")

    #
    part1 = self.disk.find_partition(self.partition_id)
    # -B : Show progress message without block detail
    # -c : output disk image
    self.argv = ["/usr/sbin/partclone.extfs", "-B", "-c", "-s", part1.device_name, "-o", "-" ]

    # Start partclone
    self.process = subprocess.Popen(self.argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self.stdout = self.process.stdout
    self.stderr = self.process.stderr
    self.read_set = [self.stderr]
    self.out = ""
    self.err = ""

    self.process2 = subprocess.Popen(self.compressor, stdin=self.process.stdout, stdout=self.outputfile, stderr=subprocess.PIPE)

    # Don't call any of super's setup.
    self.start_time = datetime.datetime.now()
    pass

  def poll(self):
    self._poll_process()

    if self.process.returncode is None:
      self.parse_partclone_progress()
    elif self.process.returncode in self.good_returncode:
      self.set_progress(99, "finishing" )
    else:
      self.set_progress(999, "failed with return code %d\n%s" % (self.process.returncode, self.err + self.compressor_err))
      pass

    chunk = drain_pipe(self.process2.stderr)
    if chunk:
      self.compressor_err = self.compressor_err + chunk
      pass
    self.process2.poll()

    if self.process2.returncode is not None:
      # compressor exited
      if self.process.returncode is None:
        # Compressor died before draining pipe. Kill the partclone.
        self.process.kill()
        # stdout points to the output file but error should be here.
        self.compressor_err = self.compressor_err + drain_pipe_completely(self.process2.stderr)
        pass
      pass

    # The task is really done both processes exited.
    if self.process.returncode in self.good_returncode and self.process2.returncode in [0]:
      self.set_progress(100, "finished" )
      pass

    pass   

  def teardown(self):
    self.outputfile.close()
    super().teardown()
    pass

  def explain(self):
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      errmsg = "*** No source partition '%s' ***\n%s" % (self.partition_id, self.disk.list_partitions())
      self.set_progress(999, errmsg)
      return errmsg
    
    return "/usr/sbin/partclone.extfs -B -c -s %s -o - | gzip > %s &2> /tmp/comp-error" % (part1.device_name, self.imagename)
  pass

#
#
#

#
#
#
class task_restore_disk_image(task_partclone):
  
  # Restore partclone image file to the first partition
  def __init__(self, description, disk=None, partition_id="Linux", source=None):
    super().__init__(description)
    self.disk = disk
    self.partition_id = partition_id
    self.source = source
    if self.source is None:
      raise Exception("bone head. it needs the source image.")
    pass

  def setup(self):
    self.linuxpart = self.disk.find_partition(self.partition_id)

    if self.linuxpart is None:
      # Partition is not there.
      self.set_progress(999, "Partition %s does not exist on %s" % (self.partition_id, self.disk.device_name))
      return

    decomp = get_file_decompression_app(self.source)
    transport_scheme = get_transport_scheme(self.source)

    if transport_scheme:
      self.argv = "wget -q -O - '%s' | %s | partclone.ext4 -r -s - -o %s" % (self.source, decomp, part1.device_name)
    else:
      if decomp == "cat":
        self.argv = "partclone.ext4 -r -s %s -o %s" % (self.source, part1.device_name)
      else:
        self.argv = "%s '%s' | partclone.ext4 -r -s - -o %s" % (decomp, self.source, part1.device_name)
        pass
      pass
    self.set_progress(0, "Restore disk image")
    pass
  pass


class task_restore_disk_image(task_partclone):
  
  def __init__(self, description, disk=None, partition_id="Linux", decompressor=["gzip"], source=None):
    super().__init__(description)
    self.source = source
    self.disk = disk
    self.partition_id = partition_id

    self.decompressor = decompressor
    self.decompressor_err = ""
    pass

  # Using partclone is different from other tasks.
  # stdout goes into compressor and the output of compressor goes out as binary file
  def setup(self):
    if not os.path.exists(self.destdir):
      self.set_progress(999, "Destination directory does not exist.")
      return

    # Final product
    self.outputfile = open(self.imagename, "wb")

    #
    part1 = self.disk.find_partition(self.partition_id)
    # -B : Show progress message without block detail
    # -c : output disk image
    self.argv = ["/usr/sbin/partclone.extfs", "-B", "-c", "-s", part1.device_name, "-o", "-" ]

    # Start partclone
    self.process = subprocess.Popen(self.argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self.stdout = self.process.stdout
    self.stderr = self.process.stderr
    self.read_set = [self.stderr]
    self.out = ""
    self.err = ""

    self.process2 = subprocess.Popen(self.compressor, stdin=self.process.stdout, stdout=self.outputfile, stderr=subprocess.PIPE)

    # Don't call any of super's setup.
    self.start_time = datetime.datetime.now()
    pass

  def poll(self):
    self._poll_process()

    if self.process.returncode is None:
      self.parse_partclone_progress()
    elif self.process.returncode in self.good_returncode:
      self.set_progress(99, "finishing" )
    else:
      self.set_progress(999, "failed with return code %d\n%s" % (self.process.returncode, self.err + self.compressor_err))
      pass

    chunk = drain_pipe(self.process2.stderr)
    if chunk:
      self.compressor_err = self.compressor_err + chunk
      pass
    self.process2.poll()

    if self.process2.returncode is not None:
      # compressor exited
      if self.process.returncode is None:
        # Compressor died before draining pipe. Kill the partclone.
        self.process.kill()
        # stdout points to the output file but error should be here.
        self.compressor_err = self.compressor_err + drain_pipe_completely(self.process2.stderr)
        pass
      pass

    # The task is really done both processes exited.
    if self.process.returncode in self.good_returncode and self.process2.returncode in [0]:
      self.set_progress(100, "finished" )
      pass

    pass   

  def teardown(self):
    self.outputfile.close()
    super().teardown()
    pass

  def explain(self):
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      errmsg = "*** No source partition '%s' ***\n%s" % (self.partition_id, self.disk.list_partitions())
      self.set_progress(999, errmsg)
      return errmsg
    
    return "/usr/sbin/partclone.extfs -B -c -s %s -o - | gzip > %s &2> /tmp/comp-error" % (part1.device_name, self.imagename)
  pass
