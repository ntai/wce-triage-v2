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

#
# Running partclone base class
#
class task_partclone(op_task_process):

  def __init__(self, description):
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

          self.set_time_estimate(elapsed + remaining)
          self.set_progress(round(completed*0.9)+10, "elapsed: %s remaining: %s" % (elapsed, remaining))
          pass
        pass
      pass
    pass
  pass

#
#
#
class task_restore_disk_image(task_partclone):
  
  # Restore partclone image file to the first partition
  def __init__(self, description, disk=None, partition_id="Linux", source=None):
    super().__init__(description)
    self.disk = disk
    self.part_id = partition_id
    self.source = source
    pass

  def setup(self):
    self.linuxpart = self.disk.find_partition(self.part_id)

    if self.linuxpart is None:
      # Partition is not there.
      self.set_progress(999, "Partition %s does not exist on %s" % (self.part_id, self.disk.device_name))
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


class task_create_disk_image(task_partclone):
  
  def __init__(self, description, disk=None, partition_id="Linux", stem_name=None, compressor="gzip", destdir="/mnt/www/wce-disk-images"):
    super().__init__(description)
    self.stem_name = stem_name
    self.disk = disk
    self.part_id = partition_id
    self.destdir = destdir
    self.compressor = compressor
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

    # Error from compressor - usually empty
    self.errorfile = open("/tmp/comp-error", "w")

    #
    part1 = self.disk.find_partition(self.part_id)
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

    self.argv2 = [self.compressor]
    self.process2 = subprocess.Popen(self.argv2, stdin=self.process.stdout, stdout=self.outputfile, stderr=self.errorfile)

    super().setup()
    pass

  def poll(self):
    super().poll()
    self.parse_partclone_progress()
    pass   

  def teardown(self):
    self.outputfile.close()
    self.errorfile.close()
    super().teardown()
    pass

  def explain(self):
    part1 = self.disk.find_partition(self.part_id)
    if part1 is None:
      return "*** No source partition ***"
    
    return "/usr/sbin/partclone.extfs -B -c -s %s -o - | gzip > %s &2> /tmp/comp-error" % (part1.device_name, self.imagename)

  pass


