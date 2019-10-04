#
# Tasks: each task is a operation. Some tasks can take a long time.
#
# For example, a task is like mkfs. As the task runs, it should produce progress
#
# By calling into diskop, it creates the plan - which is the sequence of tasks.
# exec runs through the tasks.
#

import datetime, re, subprocess, abc, os, select, time, uuid, json, traceback, shutil
from ..components.pci import find_pci_device_node
from ..components.disk import Disk, Partition, PartitionLister
from ..lib.util import drain_pipe, drain_pipe_completely, get_triage_logger
from ..lib.timeutil import *
from ..lib.grub import *
from .pplan import *
import uuid


tlog = get_triage_logger()

from .estimate import *

class op_task(object, metaclass=abc.ABCMeta):
  def __init__(self, description, encoding='utf-8', time_estimate=None, estimate_factors=None, **kwargs):
    if not isinstance(description, str):
      raise Exception("Description must be a string")
      pass
    self.kwargs = kwargs
    self.runner = None
    self.step_number = None # Runner assigns this. It's an ID for the task in the runner
    self.time_estimate = time_estimate # Time estimate is not time remaining. This is the task's whole time in seconds.
    self.encoding = encoding
    self.description = description
    self.is_started = False
    self.is_done = False
    self.progress = 0
    self.message = None # Progress message
    self.verdict = [] # Important messages
    self.start_time = None
    self.end_time = None
    self.teardown_task = False
    # file descriptors
    self.read_set = None 

    self.estimate_factors = estimate_factors
    pass

  # 0: not started
  # 1: started - running
  # 2: done - success
  # 3: done - fail
  def _get_status(self):

    if self.is_done:
      if self.progress > 100:
        return 3
      elif self.progress == 100:
        return 2
      else:
        raise Exception("bone head!")
      pass
    elif self.is_started:
      return 1
    else:
      return 0
    pass
  
  # preflight is called from runner's preflight
  def preflight(self, tasks):
    """preflight is called from runner's preflight. you get to know
       other tasks. task number is given so you know where your 
       position is in the execution, and you can adjust your estimation."""
    pass
  
  # pre_setup is called right before setup()
  def pre_setup(self):
    """pre_setup is called right before setup()."""
    self.start_time = datetime.datetime.now()
    pass
  
  # setup is called at the beginning of running.
  def setup(self):
    """setup is called at the beginning of running."""
    pass
  
  # setup failed
  def _setup_failed(self, msg):
    """setup failed is called during setup."""
    self.progress = 999
    self.messages = msg
    self.verdict.append(msg)
    self._set_end_time_now()
    self.is_done = True
    pass
  
  # teardown is called just after the run
  def teardown(self):
    """teardown is called just after the run"""
    self._set_end_time_now()
    self.is_done = True
    pass

  # This is to declare the task is teardown task.
  def _set_end_time_now(self):
    self.end_time = datetime.datetime.now()
    self.time_estimate = in_seconds(self.end_time - self.start_time)
    pass
  

  def set_teardown_task(self):
    self.teardown_task = True
    pass

  @abc.abstractmethod
  def poll(self):
    """poll is called while the execution is going on"""
    pass

  def get_description(self):
    return self.description

  def set_progress(self, progress, msg):
    self.is_started = True
    self.progress = progress
    if msg:
      self.message = msg
      if progress >= 100:
        self.verdict.append(msg)
        pass
      pass
    pass

  def _noop(self):
    self.is_started = True
    self.is_done = True
    self.progress = 100
    self.start_time = datetime.datetime.now()
    pass

  @abc.abstractmethod
  # This is called when the process is still running.
  def _estimate_progress(self, total_seconds):
    pass

  def estimate_time(self):
    if self.time_estimate is None:
      raise Exception("Time estimate is not provided.")
    return self.time_estimate

  @abc.abstractmethod
  def explain(self):
    pass

  def log(self, msg):
    self.runner.log(self, msg)
    pass

  def _estimate_progress_from_time_estimate(self, total_seconds):
    progress = 100 * total_seconds / max(1, self.time_estimate)
    if progress > 99:
      self.time_estimate = total_seconds+1
      return 99
    return progress

  pass


# Base class for Python based task
class op_task_python(op_task):
  def __init__(self, description, **kwargs):
    super().__init__(description, **kwargs)
    pass

  def setup(self):
    super().setup()
    pass
  
  def teardown(self):
    super().teardown()
    pass
  
  def poll(self):
    self.run_python()
    pass

  @abc.abstractmethod
  def run_python(self):
    pass

  pass


# Base class for simple Python 
class op_task_python_simple(op_task_python):
  def __init__(self, description, **kwargs):
    super().__init__(description, **kwargs)
    pass

  def poll(self):
    self.run_python()
    self.set_progress(100, "finished.")
    pass

  def _estimate_progress(self, total_seconds):
    return self._estimate_progress_from_time_estimate(total_seconds)

  def estimate_time(self):
    return self.time_estimate

  def explain(self):
    return "Run " + self.description
  pass



# Base class for subprocess based task
class op_task_process(op_task):
  def __init__(self, description, argv=None, select_timeout=1, **kwargs):
    super().__init__(description, **kwargs)

    self.argv = argv
    self.process = None
    self.select_timeout = select_timeout
    self.good_returncode = [0]
    self.process = None
    self.stdout = None
    self.stderr = None
    self.read_set = []
    self.out = ""
    self.err = ""
    pass

  def set_time_estimate(self, time_estimate):
    self.time_estimate = time_estimate
    pass

  def estimate_time(self):
    if self.time_estimate is None:
      raise Exception(self.description + ": Time estimate is not provided.")
    return self.time_estimate

  def setup(self):
    tlog.debug( "op_task_process Poepn: " + repr(self.argv))
    self.process = subprocess.Popen(self.argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self.stdout = self.process.stdout
    self.stderr = self.process.stderr
    self.read_set = [self.stdout, self.stderr]
    self.out = ""
    self.err = ""
    super().setup()
    pass

  def _poll_process(self):
    # check the process but not be blocked.
    self.process.poll()

    selecting = True
    while selecting:
      selecting = False
      rlist = wlist = xlist = None
      try:
        rlist, wlist, xlist = select.select(self.read_set, [], [], self.select_timeout)
      except select.error as exc:
        if exc.args[0] == errno.EINTR:
          selecting = True
          pass
        raise
      pass
      
    for pipe in self.read_set:
      if pipe in rlist:
        self._read_from_pipe(pipe)
        pass
      pass
    pass

  def _read_from_pipe(self, pipe):
    data = os.read(pipe.fileno(), 1024)
    if data == b'':
      self.read_set.remove(pipe)
      pass
    data = data.decode(self.encoding)
    if pipe == self.stdout:
      self.out = self.out + data
    else:
      self.err = self.err + data
      pass
    pass

  def _update_progress(self):
    if self.process.returncode is None:
      # Let's fake it.
      wallclock = datetime.datetime.now()
      dt = wallclock - self.start_time
      progress = self._estimate_progress(dt.total_seconds())
      if progress > 99:
        self.set_progress(999, self.kwargs.get('progress_timeout', "Timed out after %d seconds" % dt.total_seconds()))
      else:
        self.set_progress(progress, self.kwargs.get('progress_running', "Running" ))
        pass
      pass
    else:
      if self.process.returncode in self.good_returncode:
        self.set_progress(100, self.kwargs.get('progress_finished', "Finished" ) )
      else:
        self.set_progress(999, "Failed with return code %d\n%s" % (self.process.returncode, self.err))
        pass
      if self.out:
        tlog.debug("Process stdout: " + self.out)
        pass
      if self.err:
        tlog.debug("Process stderr: " + self.err)
        pass
      pass
    pass

  def _estimate_progress(self, total_seconds):
    return self._estimate_progress_from_time_estimate(total_seconds)

  def poll(self):
    self._poll_process()
    self._update_progress()
    pass

  def explain(self):
    if self.argv is None:
      raise Exception("%s has no argv" % self.description )
    return "Execute " + " ".join( [ str(arg) for arg in self.argv ] )
  pass


class op_task_process_simple(op_task_process):
  def __init__(self, description, **kwargs):
    super().__init__(description, **kwargs)
    pass

  # For simple process task, report this as half done
  def _estimate_progress(self, total_seconds):
    return self._estimate_progress_from_time_estimate(total_seconds)
  pass


# Base class for command based task
# this is to run multipe quick command line commands
# subprocess based on is for long-ish running process
# like mkfs.
# This is to run quick running commands like getting
# partition information.
class op_task_command(op_task):
  def __init__(self, description, argv=None, **kwargs):
    super().__init__(description, **kwargs)
    self.step = 0
    pass

  def estimate_time(self):
    if self.time_estimate is None:
      raise Exception("Time estimate is not provided.")
    return self.time_estimate

  def poll(self):
    pass

  def explain(self):
    return "Execute %s" % self.description
  pass

#
# mkdir uses Python os.mkdir
# I think this is truely overkill.
#
class task_mkdir(op_task_python_simple):

  def __init__(self, description, dir_path, **kwargs):
    """
    :param op: diskop instance
    :param description: description of operation
    :param dir_path: path to do mkdir

    """
    super().__init__(description, time_estimate=1, **kwargs)
    self.dir_path = dir_path
    pass

  def run_python(self):
    if not os.path.exist(self.dir_path):
      try:
        os.mkdir(self.dir_path)
        self.is_done = True
        self.progress = 100
        pass
      except Exception as exc:
        self.is_done = True
        self.progress = 999
        pass
      pass
    else:
      self.is_done = True
      self.progress = 100
      pass
    pass

  pass

#
#
#
class task_mkfs(op_task_process_simple):
  def __init__(self, description, partition=None, mkfs_opts=None, time_estimate=None, media=None, **kwargs):
    super().__init__(description, encoding='iso-8859-1', time_estimate=time_estimate, **kwargs)
    self.success_returncodes = [0]
    self.success_msg = "Creating file system succeeded."
    self.failure_msg = "Creating file system failed."
    self.part = partition
    self.mkfs_opts = mkfs_opts
    self.media = media

    if self.part.file_system in [ 'fat32', 'vfat' ]:
      #
      partname = self.part.partition_name
      if partname is None:
        partname = "EFI" if self.part.partition_type == Partition.UEFI else "DOS"
        pass

      self.argv = ["mkfs.vfat", "-n", partname]
    elif self.part.file_system == 'ext4':
      #
      partname = self.part.partition_name
      if partname is None:
        partname = "Linux"
        pass
      
      partuuid = self.part.partition_uuid
      if partuuid is None:
        partuuid = uuid.uuid4()
        pass

      self.argv = ["mkfs.ext4", "-b", "4096", "-L", partname, "-U", str(partuuid)]

      if self.media == "usb-flash":
        # No stinkin journal - USB flash media is used for triage where
        # the stick is used with read-only.
        self.argv.append('-O')
        self.argv.append('^has_journal')
        # No need to save space for emergency
        self.argv.append('-m')
        self.argv.append('0')
        # This should improve the write speed.
        self.argv.append('-E')
        self.argv.append('stripe_width=32')
        pass
      pass
    else:
      raise Exception("Unsuppoted partition type")

    if mkfs_opts:
      self.argv = self.argv + mkfs_opts
      pass

    # Finally the device name
    self.argv.append(self.part.device_name)
    pass

  def _estimate_progress(self, total_seconds):
    return self._estimate_progress_from_time_estimate(total_seconds)
  pass

#
# run mkswap
#
class task_mkswap(op_task_process_simple):
  def __init__(self, description, partition=None, time_estimate=None, **kwargs):
    super().__init__(description, encoding='iso-8859-1', time_estimate=time_estimate, **kwargs)
    self.success_returncodes = [0]
    self.success_msg = "Creating swap paritition succeeded."
    self.failure_msg = "Creating swap paritition failed."
    self.part = partition

    # Default is to let mkswap assign a UUID
    self.argv = ["mkswap", self.part.device_name]
    pass

  def _estimate_progress(self, total_seconds):
    return self._estimate_progress_from_time_estimate(total_seconds)
  pass

#
#
#
class task_unmount(op_task_process_simple):
  def __init__(self, description, disk=None, partition_id='Linux', force_unmount=False, **kwargs):
    self.disk = disk
    self.partition_id = partition_id
    self.force = force_unmount
    self.part = None
    self.partition_is_mounted = False
    super().__init__(description, argv=["/bin/umount"], time_estimate=1, **kwargs)
    pass


  def setup(self):
    self.part = self.disk.find_partition(self.partition_id)
    if self.part is None:
      self._setup_failed("No partition found. Parition id is %s" % str(self.partition_id))
      return

    self.partition_is_mounted = self.part.mounted

    self.argv = ["/bin/umount"]
    if self.force:
      self.argv.append("-f")
      pass
    self.argv.append(self.part.device_name)
    super().setup()
    pass
    

  def teardown(self):
    if self.progress == 100:
      self.part.mounted = False
    else:
      self.part.mounted = self.partition_is_mounted
      pass

    super().teardown()
    pass

  pass


#
#
#
class task_mount(op_task_process_simple):
  """mount a partition on disk"""

  def __init__(self, description, disk=None, partition_id='Linux', **kwargs):
    self.disk = disk
    self.partition_id = partition_id
    self.part = None
    super().__init__(description, argv = ["/bin/mount"], time_estimate=2, **kwargs)
    pass
  

  def setup(self):
    self.part = self.disk.find_partition(self.partition_id)
    if self.part is None:
      self.set_progress(999, "Partition with %s does not exist." % str(self.partition_id))
      return
    mount_point = self.part.get_mount_point()
    self.argv = ["/bin/mount", self.part.device_name, mount_point]

    if not os.path.exists(mount_point):
      try:
        os.makedirs(mount_point)
      except Exception as exc:
        self.set_progress(999, "Creating mount point failed. " + traceback.format_exc())
        pass
      pass
    super().setup()
    pass

  def teardown(self):
    self.part.mounted = self.progress == 100
    super().teardown()
    pass

  pass


#
# not implemented
#
class task_assign_uuid_to_partition(op_task_process_simple):

  def __init__(self, description, disk=None, partition_id=None, **kwargs):
    super().__init__(description, time_estimate=1, **kwargs)
    self.disk = disk
    self.partition_id = partition_id
    pass
  

  def setup(self):
    self.part = self.disk.find_partition(self.partition_id)
    if self.part is None:
      self.set_progress(999, "Partition %s on disk %d is not found." % (self.partition_id, self.disk.device_name))
      return

    if self.part.partition_type == "83":
      self.argv = ["tune2fs", "%s1" % part.device_name, "-U", part.partition_uuid, "-L", "/"]
    elif part.partition_type == "C":
      self.argv = ["mkswap", "-U", disk.uuid2, "%s5" % disk.device_name]
      pass
    else:
      raise Exception("unsupported partition type")
    super().setup()
    pass

  pass


def task_get_uuid_from_partition(op_task_process_simple):
  def __init__(self, description, partition=None, **kwargs):
    self.part = partition
    arg = ["/sbin/blkid", part.device_name]
    super().__init__(description, argv=arg, time_estimate=2, **kwargs)
    pass

  def setup(self):
    self.part.partition_uuid = None
    pass

  def poll(self):
    super().poll()

    if self.progress == 100:
      blkid_re = re.compile(r'/dev/(\w+)1: LABEL="([/\w\.\d]+)" UUID="([\w\d]+-[\w\d]+-[\w\d]+-[\w\d]+-[\w\d]+)" TYPE="([\w\d]+)"')
      for line in safe_string(self.out).splitlines():
        m = blkid_re.match(line)
        if m:
          self.part.partition_uuid = m.group(2)
          break
      pass
    pass
  pass


#
# Run fsck on a partition
#
class task_fsck(op_task_process):
  #
  def __init__(self, description, disk=None, partition_id=None, payload_size=None, **kwargs):
    self.disk = disk
    self.partition_id = partition_id
    self.payload_size = payload_size
    speed = self.disk.estimate_speed("fsck")
    estimate_size = self.disk.get_byte_size() if self.payload_size is None else self.payload_size
    super().__init__(description, argv=["/sbin/e2fsck", "-f", "-y", disk.device_name, partition_id], time_estimate=estimate_size/speed+2, **kwargs)
    pass

  def setup(self):
    #
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      error_message = "fsck: disk %s partition %s is not found" % (self.disk.device_name, self.partition_id)
      tlog.warn(error_message)
      self._setup_failed(error_message)
      return

    self.argv = ["/sbin/e2fsck", "-f", "-y", part1.device_name]
    super().setup()
    pass
   
  def _estimate_progress(self, total_seconds):
    return self._estimate_progress_from_time_estimate(total_seconds)

  pass


class task_expand_partition(op_task_process):
  #
  def __init__(self, description, disk=None, partition_id=None, **kwargs):
    self.disk = disk
    self.partition_id = partition_id

    # obviously, expanding does small writes but amount is much smaller than the disk
    expand_fs_write = self.disk.get_byte_size() / 100 / 1024
    speed = self.disk.estimate_speed("expand")
    super().__init__(description,
                     argv = ["resize2fs", disk.device_name, str(partition_id)],
                     time_estimate = expand_fs_write / speed + 2, **kwargs) # FIXME time_estimate is bogus
    pass

  def setup(self):
    #
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      self.set_progress(999, "Partition %s does not exist on %s" % (self.partition_id, self.disk.device_name))
      return

    self.argv = ["resize2fs", part1.device_name]
    super().setup()
    return

  def _estimate_progress(self, total_seconds):
    return self._estimate_progress_from_time_estimate(total_seconds)

  pass


class task_shrink_partition(op_task_process):
  #
  def __init__(self, description, disk=None, partition_id=None, **kwargs):
    self.disk = disk
    self.partition_id = partition_id

    # time estiamte for shrinking partition is not possible.
    # it might move some files and there is no way of knowing
    shrink_fs_write = self.disk.get_byte_size() / 1024
    speed = self.disk.estimate_speed("shrink")

    super().__init__(description,
                     time_estimate=shrink_fs_write / speed, # FIXME: still bogus estimate
                     argv=["resize2fs", "-M", disk.device_name, partition_id], **kwargs)
    pass

  def setup(self):
    #
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      self.set_progress(999, "Partition %s does not exist on %s" % (self.partition_id, self.disk.device_name))
      return

    self.argv = ["resize2fs", "-M", part1.device_name]
    super().setup()
    return

  def _estimate_progress(self, total_seconds):
    return self._estimate_progress_from_time_estimate(total_seconds)

  pass


class task_create_wce_tag(op_task_python_simple):
  def __init__(self, description, disk=None, source=None, **kwargs):
    super().__init__(description, time_estimate=1, **kwargs)
    self.disk = disk
    self.source = source
    pass
  
  def run_python(self):
    # Set up the /etc/wce-release file
    release = open(self.disk.wce_release_file, "w+")
    release.write("wce-contents: %s\n" % get_filename_stem(self.source))
    release.write("installer-version: %s\n" % installer_version)
    release.write("installation-date: %s\n" % datetime.datetime.isoformat( datetime.datetime.utcnow() ))
    release.close()
    self.set_progress(100, "WCE release tag written")
    pass
  
  pass


#  Remove files
class task_remove_files(op_task_python_simple):
    #
  def __init__(self, description, disk=None, files=None, partition_id='Linux', **kwargs):
    super().__init__(description, **kwargs)
    self.disk = disk
    self.partition_id = partition_id
    self.files = [] if files is None else files
    pass

  def run_python(self):
    part = self.disk.find_partition(self.partition_id)
    if part is None:
      self.set_progress(999, 'Partition does not exist.')
      return
    
    rootpath = part.get_mount_point()
    n = len(self.files)
    i = 0
    # Protect myself from stupidity
    toplevels = os.listdir("/")
    toplevels.append("")
    # except swapfile! go ahead and remove swapfile if you need
    try:
      toplevels.remove("swapfile")
    except:
      pass
    for filename in self.files:
      if filename in toplevels:
        continue
      path = os.path.join(rootpath, filename)
      i = i + 1
      if os.path.exists(path):
        try:
          if os.path.isdir(path):
            shutil.rmtree(path)
            tlog.debug("Dir %s deleted." % path)
            pass
          else:
            os.remove(path)
            tlog.debug("File %s deleted." % path)
            pass
          pass
        except:
          pass
        pass
      else:
        tlog.debug("Path %s does not exist." % path)
        pass
      pass
    pass
  pass


# This is to purge the persistent rules for network and cd devices so that the clone
# installation will have correct device names
class task_remove_persistent_rules(task_remove_files):
    #
  def __init__(self, description, disk=None, partition_id='Linux', **kwargs):
    files = ["etc/wce-release",
             "var/lib/world-computer-exchange/access-timestamp",
             "var/lib/world-computer-exchange/computer-uuid",
             "etc/udev/rules.d/70-persistent-cd.rules",
             "etc/udev/rules.d/70-persistent-net.rules"]
    super().__init__(description, disk=disk, partition_id=partition_id, files=files, time_estimate=1, **kwargs)
    pass
  pass


# This is to purge the system logs. It's no use to restored machines.
class task_remove_logs(task_remove_files):
    #
  def __init__(self, description, disk=None, partition_id='Linux', **kwargs):
    files = [ "var/log/" + filename for filename in ["kern.log", "syslog", "alternatives.log", "auth.log",  "fontconfig.log", "dpkg.log", "boot.log", "unattended-upgrades/unattended-upgrades-shutdown.log", "apt/history.log", "apt/term.log", "var/log/installer" ]]
    super().__init__(description, disk=disk, partition_id=partition_id, files=files, time_estimate=1, **kwargs)
    pass
  pass


# Installing MBR on disk
class task_install_mbr(op_task_process_simple):
  def __init__(self, description, disk=None, **kwargs):
    self.disk = disk
    argv = ["/sbin/install-mbr", "-r", "-e3", self.disk.device_name]
    super().__init__(description, argv, time_estimate=1, **kwargs)
    pass
  pass


#
# Run parted and create partition entities.
# You need to run refresh partitions in order to get the
# file system UUID, so use following two tasks in
# succession.
#
class task_fetch_partitions(op_task_process_simple):
  """fetches partitions from disk and creates parition instances."""

  #                          1:    2:           3:           4:           5:fs  6:name  7:flags   

  def __init__(self, description, disk=None, **kwargs):
    self.disk = disk
    self.lister = PartitionLister(disk)
    super().__init__(description, argv=self.lister.argv, time_estimate=1, **kwargs)
    pass
  
  def poll(self):
    super().poll()

    if self.progress == 100:
      self.lister.set_parted_output(self.out, self.err)
      self.lister.parse_parted_output()

      if len(self.disk.partitions) == 0:
        self.set_progress(999, 'No partion found.')
        pass
      pass
    pass
  pass
    

class task_refresh_partitions(op_task_command):
  """refreshes (reads) partitions from disk."""
  
  props = {'PARTUUID':  'partition_uuid',
           # 
           'TYPE':      'partition_type',
           'PARTLABEL': 'partition_name',
           'UUID':      'fs_uuid'
           }
  tagvalre = re.compile('\s*(\w+)="([^"]+)"')

  def __init__(self, description, disk=None, **kwargs):
    super().__init__(description, encoding='iso-8859-1', **kwargs)
    self.disk = disk
    self.time_estimate = 2
    self.ext4_count = 0
    pass
  
  def poll(self):
    super().poll()

    if self.step >= len(self.disk.partitions):
      self.set_progress(100, "%s finished." % self.description)
      for part in self.disk.partitions:
        self.verdict.append("Partition %d %s (%s) - UUID %s." % (part.partition_number, part.partition_type, part.partition_name, part.fs_uuid))
        pass
      return

    part = self.disk.partitions[self.step]
    self.step += 1
    part.partition_number = self.step

    result = subprocess.run([ '/sbin/blkid', part.device_name ],
                              timeout=10, encoding=self.encoding,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out = result.stdout
    devdelim = out.find(':')
    # device_name should match with the part.device_name
    device_name = out[:devdelim]

    # The rest is key=value with space delimiter.
    tokens = self.tagvalre.split(out[devdelim+1:].strip())
    index = 0
    tag = None
    value = None
    for token in tokens:
      if token == '':
        continue
      
      if tag is None:
        tag = token
        continue

      attrname = self.props.get(tag)
      if attrname is not None:
        part.__setattr__(attrname, token)
        pass
      tag = None
      pass

    #
    self.log("Partition %d %s (%s) - UUID %s." % (part.partition_number, part.partition_type, part.partition_name, part.fs_uuid))

    if part.partition_type == 'ext4':
      self.ext4_count += 1
      # If this is the first linux ext4 partition, and has no name, name it 'Linux'
      if not part.partition_name and self.ext4_count == 1:
        part.partition_name = 'Linux'
        pass
      pass
    pass

  def _estimate_progress(self, total_seconds):
    return int(99 / len(self.disk.partitions) * self.step)

  pass

#
#
#
class task_set_partition_uuid(op_task_process_simple):
  def __init__(self, description, disk=None, partition_id=None, time_estimate=6, **kwargs):
    self.disk = disk
    self.partition_id = partition_id
    # argv is a placeholder
    super().__init__(description, encoding='iso-8859-1', time_estimate=3, argv=["tune2fs", "-f", "-U", disk.device_name, partition_id], **kwargs)
    pass
  
  def setup(self):
    #
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      self.set_progress(999, "Partition %s does not exist on %s" % (self.partition_id, self.disk.device_name))
      return
    self.argv = ["tune2fs", "-f", "-U", part1.fs_uuid, part1.device_name]
    super().setup()
    return

  pass


#
#
#
class task_install_syslinux(op_task_process):
  """Installs syslinux on the device"""
  def __init__(self, description, disk=None, **kwargs):
    argv = ["/usr/bin/syslinux", "-maf", disk.device_name]
    self.disk = disk
    super().__init__(description, argv, time_estimate=1, **kwargs)
    pass
  pass



#
# Install GRUB boot loader
#
class task_install_grub(op_task_process):
  script_path_template = "%s/tmp/bless.sh"

  def __init__(self, description, disk=None, detected_videos=None, partition_id='Linux', **kwargs):
    # Disk to bless
    self.disk = disk
    self.partition_id = partition_id
    (self.n_nvidia, self.n_ati, self.n_vga) = detected_videos
    self.linuxpart = None
    self.mount_dir = None
    self.script_path = None
    self.script = None

    # FIXME: Time estimate is very different between USB stick and hard disk.
    # grub copies a bunch of files
    grub_read_size = 4 * 2**20
    grub_write_size = 4 * 2**20
    grub_size = grub_read_size + grub_write_size
    speed = self.disk.estimate_speed("grub")
    # argv is a placeholder
    super().__init__(description, argv=['/usr/sbin/grub-install', disk.device_name], time_estimate=grub_size/speed, **kwargs)
    pass

  #
  def setup(self):
    # 
    self.linuxpart = self.disk.find_partition(self.partition_id)
    if self.linuxpart is None:
      self._setup_failed("No partition found. Parition id is %s" % str(self.partition_id))
      return

    # IOW, the disk should be mounted, or else, I'm in big problem
    if not self.linuxpart.mounted:
      self._setup_failed("Linux partition is not mounted.")
      return

    # Blesser
    self.mount_dir = self.linuxpart.get_mount_point()
    self.script_path = self.script_path_template % self.mount_dir

    #
    # grub-install doesn't work without chroot
    # For wifi and video drivers, it needs adding or removing packages.
    # To do so, you need the chroot and run apt.
    #
    self.script = [
      "#!/bin/sh",
      "mount -t proc none /proc",
      "mount -t sysfs none /sys",
      "mount -t devpts none /dev/pts",
      "#"]

    # Things to do is installing grub
    # Only see the mounted disk, and no other device
    self.script.append("export GRUB_DISABLE_OS_PROBER=true")
    self.script.append("/usr/sbin/grub-install -v --target=i386-pc --force %s" % self.disk.device_name)

    if self.n_ati > 0:
      self.script.append('# If this machine has ATI video, get rid of other video drivers that can get in its way.')
      self.script.append("apt-get -q -y --force-yes purge `dpkg --get-selections | cut -f 1 | grep -v xorg | grep nvidia-`")
      pass

    self.script.append('# Set up the grub.cfg')
    self.script.append('chmod +rw /boot/grub/grub.cfg')
    self.script.append('grub-mkconfig -o /boot/grub/grub.cfg')

    self.script.append('# clean up')
    self.script.append('umount /proc || umount -lf /proc')
    self.script.append('umount /sys')
    self.script.append('umount /dev/pts')
    self.script.append('# script end')

    # Write out the bless script
    script_file = open(self.script_path, "w")
    script_file.write("\n".join(self.script))
    script_file.close()
    os.chmod(self.script_path, 0o755)

    # Set up the /dev for chroot
    subprocess.run("mount --bind /dev/ %s/dev" % self.mount_dir, shell=True)

    # Run the blessing script with chroot
    self.argv = ["/usr/sbin/chroot",  self.mount_dir, "/bin/sh", self.script_path_template % ""]

    super().setup()
    pass

  # grub-install may take long time. time out only when
  # it takes 2x of time estmate.
  def _estimate_progress(self, total_seconds):
    progress = int(100.0 * total_seconds / max(1, self.time_estimate))
    if progress > 1000:
      return 999
    elif progress > 99:
      return 99
    else:
      return progress
    pass

  def teardown(self):
    super().teardown()
    # tear down the /dev for chroot
    subprocess.run("umount %s/dev" % self.mount_dir, shell=True)
    if self.script_path:
      try:
        os.unlink(self.script_path)
      except:
        pass
      pass

    bless_log=open("/tmp/bless.log", "w")
    if self.out:
      bless_log.write("stdout\n")
      bless_log.write(self.out)
      pass
    
    if self.err:
      bless_log.write("stderr\n")
      bless_log.write(self.err)
      pass
    bless_log.close()
    pass

  pass

#
# Zero the first 1MB of device. This clears off the
# partition's magic number, etc. Without this, os-prober
# can be very confused.
#
class task_zero_partition(op_task_python_simple):
  def __init__(self, description, partition=None, **kwargs):
    super().__init__(description, time_estimate=1, **kwargs)
    self.partition = partition
    pass

  def run_python(self):
    fd = open(self.partition.device_name, "wb")
    for ix in range(0, 16):
      fd.write(bytes(65536))
      pass
    fd.close()
    pass

  pass

fstab_template = """# /etc/fstab: static file system information.
#
# This file is auto-generated by WCE installation.
#
# Use 'blkid -o value -s UUID' to print the universally unique identifier
# for a device; this may be used with UUID= as a more robust way to name
# devices that works even if disks are added and removed. See fstab(5).
#
# <file system> <mount point>   <type>  <options>       <dump>  <pass>
proc            /proc           proc    nodev,noexec,nosuid 0       0
#
UUID=%s /               ext4    errors=remount-ro 0       1
"""

# UUID should be available after re-fetching partition info.
# Original was 9ABD-4363
efi_template = """# /boot/efi was on /dev/sda1 during installation
UUID=%s  /boot/efi       vfat    umask=0077      0       1
"""

swap_template = """# swap partition. should match with blkid output.
UUID=%s none            swap    sw              0       0
"""

#
# Create various files for blessed installation
#
class task_finalize_disk(op_task_python_simple):
  """sets up /etc/fstab and /etc/hostname.
fstab is always adjusted to the new partition UUID.
new hostname set up is only done if the new hostname is provided. If it's None, it's untouched.
"""
  def __init__(self, description, disk=None, newhostname=None, partition_id='Linux', efi_id = None, wce_share_url=None, **kwargs):
    super().__init__(description, time_estimate=1, **kwargs)
    self.newhostname = newhostname
    self.disk = disk
    self.partition_id = partition_id
    self.efi_id = efi_id
    self.efi_part = None
    self.swappart = None
    self.mount_dir = None
    self.wce_share_url = wce_share_url
    pass
   

  def run_python(self):
    #
    self.linuxpart = self.disk.find_partition(self.partition_id)
    if self.linuxpart is None:
      msg = "Partition with %s does not exist." % str(self.partition_id)
      self.set_progress(999, msg)

      tlog.debug("part n = %d" % len(self.disk.partitions))
      for part in self.disk.partitions:
        tlog.debug( str(part))
        pass
      raise Exception(msg)

    self.efi_part = self.disk.find_partition(EFI_NAME)
    self.swappart = self.disk.find_partition_by_type(Partition.SWAP)
    self.mount_dir = self.linuxpart.get_mount_point()

    # patch up the restore
    fstab = open("%s/etc/fstab" % self.mount_dir, "w")
    fstab.write(fstab_template % (self.linuxpart.fs_uuid))
    if self.efi_part:
      fstab.write(efi_template % self.efi_part.fs_uuid)
      pass
    if self.swappart:
      fstab.write(swap_template % (self.swappart.fs_uuid))
      pass
    fstab.close()

    #
    # New hostname
    #
    if self.newhostname:
      # Set up the /etc/hostname
      etc_hostname_filename = "%s/etc/hostname" % self.mount_dir
      hostname_file = open(etc_hostname_filename, "w")
      hostname_file.write("%s\n" % self.newhostname)
      hostname_file.close()

      # Set up the /etc/hosts file
      etc_hosts_filename = "%s/etc/hosts" % self.mount_dir
      hosts = open(etc_hosts_filename, "r")
      lines = hosts.readlines()
      hosts.close()
      hosts = open(etc_hosts_filename, "w")

      this_host = re.compile(r"127\.0\.1\.1\s+[a-z_A-Z0-9]+\n")
      for line in lines:
        m = this_host.match(line)
        if m:
          hosts.write("127.0.1.1\t%s\n" % self.newhostname)
        else:
          hosts.write(line)
          pass
        pass
      hosts.close()

      self.log("Hostname in %s/etc is updated with %s." % (self.mount_dir, self.newhostname))
      pass

    # Set the wce_share_url to /etc/default/grub
    if self.wce_share_url is not None:
      grub_file = "%s/etc/default/grub" % self.mount_dir
      updated, contents = grub_set_wce_share(grub_file, self.wce_share_url)
      if updated:
        grub = open(grub_file, "w")
        grub.write(contents)
        grub.close()
        pass
      pass

    #
    # Remove the WCE follow up files
    # 
    for removing in ["%s/var/lib/world-computer-exchange/computer-uuid",
                     "%s/var/lib/world-computer-exchange/access-timestamp"]:
      try:
        os.unlink( removing % self.mount_dir)
      except:
        # No big deal if the file isn't there or failed to remove.
        pass
      pass
    pass
  pass


class task_finalize_disk_aux(op_task_python):
  def __init__(self, description, disk=None, newhostname=None, partition_id='Linux', **kwargs):
    super().__init__(description, time_estimate=1, **kwargs)
    self.disk = disk
    self.linuxpart = self.disk.find_partition(partition_id)
    self.newhostname = newhostname
    pass
   
  def run_python(self):
    #
    # Patch up the grub.cfg just in case the "/dev/disk/by-uuid/%s" % 
    # self.uuid1 does not exist. If that happens, grub-mkconfig 
    # genertes the device name based grub.cfg which is bad.
    #
    # This should fix up the most of unbootable disk imaging.
    #
    root_fs = "UUID=%s" % part1.uuid
    linux_re = re.compile(r'(\s+linux\s+[^ ]+\s+root=)([^ ]+)(\s+ro .*)')
    grub_cfg_file = open("%s/boot/grub/grub.cfg" % self.mount_dir)
    grub_cfg = grub_cfg_file.readlines()
    grub_cfg_file.close()
    grub_cfg_file = open("%s/boot/grub/grub.cfg" % self.mount_dir, "w")
    for line in grub_cfg:
      m = linux_re.match(line)
      if m:
        grub_cfg_file.write("%s%s%s\n" % (m.group(1), root_fs, m.group(3)))
      else:
        grub_cfg_file.write(line)
        pass
      pass
    grub_cfg_file.close()
    pass
  pass

#
# Adjust grub in EFI 
#
EFI_ubuntu_grub_template = """search.fs_uuid {Linux_UUID} root hd0,gpt{Linux_part_no} 
set prefix=($root)'/boot/grub'
configfile $prefix/grub.cfg
"""

class task_finalize_efi(op_task_python_simple):
  def __init__(self, description, disk=None, partition_id='Linux', efi_id = EFI_NAME, **kwargs):
    super().__init__(description, time_estimate=1, **kwargs)
    self.disk = disk
    self.partition_id = partition_id
    self.efi_id = efi_id
    pass
   

  def run_python(self):
    #
    self.linuxpart = self.disk.find_partition(self.partition_id)
    if self.linuxpart is None:
      msg = "Partition with %s does not exist." % str(self.partition_id)
      self.set_progress(999, msg)

      tlog.debug("part n = %d" % len(self.disk.partitions))
      for part in self.disk.partitions:
        tlog.debug( str(part))
        pass
      raise Exception(msg)

    self.efi_part = self.disk.find_partition(EFI_NAME)
    if self.efi_part is None:
      msg = "EFI Partition with %s does not exist." % str(self.efi_id)
      self.set_progress(999, msg)

      tlog.debug("part n = %d" % len(self.disk.partitions))
      for part in self.disk.partitions:
        tlog.debug( str(part))
        pass
      raise Exception(msg)

    self.mount_dir = self.linuxpart.get_mount_point()
    self.efi_dir = self.efi_part.get_mount_point()

    # patch up the grub.cfg
    grub_cfg = open("%s/EFI/ubuntu/grub.cfg" % self.efi_dir, "w")
    grub_cfg.write(EFI_ubuntu_grub_template.format(Linux_UUID=self.linuxpart.fs_uuid, Linux_part_no=self.linuxpart.partition_number))
    grub_cfg.close()
    pass
  pass

#
#
#
class task_mount_nfs_destination(op_task_process):

  def __init__(self, description, **kwargs):
    super().__init__(description, **kwargs)
    pass
  
  def setup(self):
    if not is_network_connected():
      self.set_progress(999, "Network is not working.")
      return
    
    if nfs_server is None:
      nfs_server = get_router_ip_address()
      pass

    if not nfs_server:
      self.set_progress(999, "No NFS server")
      return

    # Mount the NFS to /mnt/www
    if not os.path.exists("/mnt/www"):
      try:
        os.mkdir("/mnt/www")
      except:
        self.set_progress(999, "Failed to mkdir mount point.")
        pass
      pass

    self.argv = [ "mount", "-t", "nfs",  "%s:/var/www" %nfs_server, "/mnt/www"]
    super().setup()
    pass
  pass

#
# Sleep task - for testing
#
class task_sleep(op_task_process):
  def __init__(self, description, duration, **kwargs):
    super().__init__(description, **kwargs)
    self.duration = duration
    self.argv = ['sleep', str(duration)]
    pass

  def _estimate_progress(self, total_seconds):
    wallclock = datetime.datetime.now()
    dt = wallclock - self.start_time
    return 100 * (dt.total_seconds()/self.duration)
  pass


# Package uninsall base class
class task_uninstall_package(op_task_process):

  def __init__(self, op, description, packages=None, **kwargs):
    super().__init__(op, description, **kwargs)
    self.packages = packages
    pass
  
  def setup(self):
    if self.packages:
      self.argv = [ "apt", "purge", "-y" ] + self.packages
      super().setup()
      pass
    pass

  pass

#
# Uninstall Broadcom STA
#
class task_uninstall_bcmwl(task_uninstall_package):
  
  def __init__(self, op, description, packages=None, **kwargs):
    super().__init__(op, description, **kwargs)
    pass
  
  def setup(self):
    if find_pci_device_node([0x14e4], [0x4312]):
      self.packages = ['bcmwl-kernel-source']
      super().setup()
      pass
    else:
      self._noop()
      pass
    pass
  pass

#
#
#
class op_task_wipe_disk(op_task_process):
  #
  def __init__(self, description, disk=None, short=False, **kwargs):
    self.disk = disk
    argv = ["python3", "-m", "wce_triage.bin.zerowipe"]

    estimate = 2
    if short:
      argv.append("-s")
    else:
      estimate += self.disk.get_byte_size()/40000000
      pass
    argv.append(disk.device_name)
    super().__init__(description, argv=argv, time_estimate=estimate, **kwargs)
    pass

  def poll(self):
    super().poll()

    # nothing to look at.
    if len(self.err) == 0:
      return

    # look for a line
    while True:
      newline = self.err.find('\n')
      if newline < 0:
        break
      line = self.err[:newline]
      self.err = self.err[newline+1:]

      # what's coming out from zerowipe is json.
      report = None
      try:
        # From wiper, this is a complete "event" + "message", but I don't need the event
        # part for a task.
        report = json.loads(line)
        # it's a bit confusing but this message is the payload for status
        message = report.get("message") 
        self.set_progress(message.get('progress', 50), message.get('message', 'Wipe is running.'))
        self.time_estimate = message.get("runEstimate")
        pass
      except Exception as exc:
        tlog.info("bad wipe ouptut? " + traceback.format_exc() + "\n" + line)
        pass
      pass

    while True:
      newline = self.out.find('\n')
      if newline < 0:
        break
      line = self.out[:newline]
      self.out = self.out[newline+1:]
      self.log(line)
      pass
    pass
  pass


class task_sync_partitions(op_task_process_simple):
  """After creating partitions, let kernel sync up and create device files.
Pretty often, the following mkfs fails due to kernel not acknowledging the
new partitions and partition device file not read for the follwing mkks."""

  def __init__(self, description, disk=None, n_partitions=None, **kwargs):

    argv = ['partprobe']
    self.disk = disk
    self.n_partitions = n_partitions
    super().__init__(description,
                     argv=argv,
                     progress_finished="Partitions synced with kernel",
                     **kwargs)
    pass

  def poll(self):
    self._poll_process()
    if self.process.returncode is None:
      self._update_progress()
      pass
    else:
      if self.process.returncode in self.good_returncode:
        if self.confirm_partition_device_files():
          self._update_progress()
          pass
        else:
          tlog.debug("{dev}{part}".format(dev=self.disk.device_name, part=self.n_partitions) + " Disks: " + ",".join([ node for node in os.listdir('/dev') if node[:2] == 'sd']))
          self.set_progress(99, self.kwargs.get('progress_synching', "Syncing with OS" ) )
          pass
        pass
      else:
        self._update_progress()
        pass
      pass
    pass

  def confirm_partition_device_files(self):
    """see the partition device files appeared"""
    for part_no in range(self.n_partitions):
      part_device_name = "%s%d" % (self.disk.device_name, part_no+1)
      if not os.path.exists(part_device_name):
        return False
      pass
    return True

  pass

