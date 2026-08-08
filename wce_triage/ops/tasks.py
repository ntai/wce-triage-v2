#
# Tasks: each task is a operation. Some tasks can take a long time.
#
# For example, a task is like mkfs. As the task runs, it should produce progress
#
# By calling into diskop, it creates the plan - which is the sequence of tasks.
# exec runs through the tasks.
#

import datetime, re, subprocess, abc, os, select, uuid, json, traceback, shutil
import signal
import struct
import errno
import sys
from typing import Optional
import io

from .run_state import RunState
from .protocol import ProgressEnvelope, TaskStatus, split_lines
from ..components.pci import find_pci_device_node
from ..components.disk import Partition, PartitionLister
from ..components.network import detect_net_devices, get_router_ip_address
from ..lib.util import get_triage_logger, get_filename_stem
from ..lib.timeutil import in_seconds
from ..lib.grub import grub_config
from .pplan import EFI_NAME
from ..version import TRIAGE_VERSION, TRIAGE_TIMESTAMP
from ..const import const

tlog = get_triage_logger()


class op_task(object, metaclass=abc.ABCMeta):
  """Task is a unit of oction"""

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
  def _get_status(self) -> int:
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
    return 0

  
  # preflight is called from runner's preflight
  def preflight(self, tasks) -> None:
    """preflight is called from runner's preflight. you get to know
       other tasks. task number is given so you know where your 
       position is in the execution, and you can adjust your estimation."""
    pass
  
  # pre_setup is called right before setup()
  def pre_setup(self) -> None:
    """pre_setup is called right before setup()."""
    self.start_time = datetime.datetime.now()
    pass
  
  # setup is called at the beginning of running.
  def setup(self) -> None:
    """setup is called at the beginning of running."""
    pass
  
  # setup failed
  def _setup_failed(self, msg) -> None:
    """setup failed is called during setup."""
    self.progress = 999
    self.messages = msg
    self.verdict.append(msg)
    self._set_end_time_now()
    self.is_done = True
    pass
  
  # teardown is called just after the run
  def teardown(self) -> None:
    """teardown is called just after the run"""
    self._set_end_time_now()
    self.is_done = True
    pass

  # This is to declare the task is teardown task.
  def _set_end_time_now(self) -> None:
    self.end_time = datetime.datetime.now()
    self.time_estimate = in_seconds(self.end_time - self.start_time)
    pass
  

  def set_teardown_task(self) -> None:
    """Declare the task is a teardown task. Teardown task is always executed even in the failed run."""
    self.teardown_task = True
    pass

  @abc.abstractmethod
  def poll(self):
    """poll is called while the execution is going on"""
    pass

  def get_description(self):
    return self.description

  def describe_subtasks(self, current_time):
    """Override when one task represents several parallel logical operations
    (e.g. one process wiping several disks at once). Returning a non-None list
    of protocol.TaskStatus makes the runner report expand this task into that
    list instead of describing it as a single TaskStatus."""
    return None

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


  def set_task_finished_message(self, msg):
    """This is to change the message for finished state."""
    self.kwargs['progress_finished'] = "No disk image files to delete"
    pass

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
    try:
      self.run_python()
    except Exception as exc:
      msg = traceback.format_exc()
      self.verdict.append(msg)
      raise exc

    if self.progress < 100:
      self.set_progress(100, "Finished")
      pass
    pass

  def _estimate_progress(self, total_seconds):
    return self._estimate_progress_from_time_estimate(total_seconds)

  def estimate_time(self):
    return self.time_estimate

  def explain(self):
    return "Run " + self.description

  @abc.abstractmethod
  def run_python(self):
    pass
  pass



# Base class for subprocess based task
class op_task_process(op_task):

  argv: list
  process: subprocess.Popen
  stdout: io.BufferedReader
  stderr: io.BufferedReader
  _kill_count: int
  select_timeout: float
  good_returncode: list
  read_set: list
  out: str
  err: str

  def __init__(self, description, argv=None, select_timeout=1, **kwargs):
    super().__init__(description, **kwargs)

    self.argv = argv
    self.process = None
    self.stdout = None
    self.stderr = None
    self._kill_count = 0
    self.select_timeout = select_timeout
    self.good_returncode = [0]
    self.read_set = []
    self.out = ""
    self.err = ""
    pass

  def is_success(self) -> Optional[bool]:
    if self.process.returncode is None:
      return None
    return self.process.returncode in self.good_returncode

  def set_time_estimate(self, time_estimate):
    self.time_estimate = time_estimate
    pass

  def estimate_time(self):
    if self.time_estimate is None:
      raise Exception(self.description + ": Time estimate is not provided.")
    return self.time_estimate

  def preflight(self, tasks):
    super().preflight(tasks)
    pass

  def setup(self):
    tlog.debug( "op_task_process Poepn: " + repr(self.argv))
    self.verdict.append("Process: " + repr(self.argv))
    self.process = subprocess.Popen(self.argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    self.stdout = self.process.stdout
    self.stderr = self.process.stderr
    self.read_set = [self.stdout, self.stderr]
    self.out = ""
    self.err = ""
    super().setup()
    assert(self.argv is not None)
    pass


  def _poll_process(self):
    #
    if self.runner and self.runner.state != RunState.Running:
      if self._kill_count == 0:
        self._kill_count += 1
        if self.process:
          tlog.info("Sending SIGINT to %s" % self.description)
          self.process.send_signal(signal.SIGINT)
          pass
        pass
      pass

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
    completion = self.is_success()
    if completion is None:  # still running
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
    elif completion:  # success
      self.set_progress(100, self.kwargs.get('progress_finished', "Finished" ) )
      if self.out:
        out_msg = "Process stdout: " + self.out
        tlog.info(out_msg)
        pass
      if self.err:
        err_msg = "Process stderr: " + self.err
        tlog.info(err_msg)
        pass
      pass
    else:  # failed
      if self._kill_count > 0:
        self.set_progress(999, "Task %s killed" % self.description)
        log_msg = "%s is killed." % (self.description)
      else:
        self.set_progress(999, "Failed with return code %d" % (self.process.returncode))
        log_msg = "%s failed with return code %d" % (self.description, self.process.returncode)
        pass
      if self.out:
        log_msg = log_msg + "\nstdout\n" + self.out
        pass
      if self.err:
        log_msg = log_msg + "\nstderr\n" + self.err
        pass
      tlog.info(log_msg)
      pass

    if completion is not None:
      if self.out:
        self.verdict.append("stdout: " + self.out)
        pass
      if self.err:
        self.verdict.append("stderr: " + self.err)
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
  def __init__(self, description, argv=None, **kwargs):
    super().__init__(description, argv=argv, **kwargs)
    pass

  # For simple process task, report this as half done
  def _estimate_progress(self, total_seconds):
    return self._estimate_progress_from_time_estimate(total_seconds)
  pass


# Base class for command based task
# this is to run multiple quick command line commands
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
    kwargs["time_estimate"] = kwargs.get("time_estimate", 1)
    super().__init__(description, **kwargs)
    self.dir_path = dir_path
    pass

  def run_python(self):
    if not os.path.exists(self.dir_path):
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
  def __init__(self, description, partition:Partition=None, mkfs_opts=None, media=None, **kwargs):
    time_estimate = 10
    if partition:
      part_size = partition.get_parition_size()
      if part_size:
        time_estimate = round(part_size / 1024.0 / 1024 / 1024 / 10) + 5
        pass
      pass
    kwargs["time_estimate"] = kwargs.get("time_estimate", time_estimate)
    super().__init__(description, encoding='iso-8859-1', **kwargs)
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
        partname = "EFI" if self.part.partcode == Partition.UEFI else "DOS"
        pass

      self.argv = ["mkfs.vfat", "-F", "32", "-n", partname]
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
  def __init__(self, description, partition=None, **kwargs):
    kwargs["time_estimate"] = kwargs.get("time_estimate", 2)
    super().__init__(description, encoding='iso-8859-1', **kwargs)
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
    kwargs["time_estimate"] = kwargs.get("time_estimate", 1)
    self.disk = disk
    self.partition_id = partition_id
    self.force = force_unmount
    self.part = None
    self.partition_is_mounted = False
    super().__init__(description, argv=["/bin/umount"], **kwargs)
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

  def __init__(self, description, disk=None, partition_id='Linux', add_mount_point=None, **kwargs):
    kwargs["time_estimate"] = kwargs.get("time_estimate", 1)
    self.disk = disk
    self.partition_id = partition_id
    self.part = None
    self.add_mount_point = add_mount_point
    super().__init__(description, argv = ["/bin/mount"], **kwargs)
    pass
  

  def setup(self):
    self.part = self.disk.find_partition(self.partition_id)
    if self.part is None:
      self.set_progress(999, "Partition with %s does not exist." % str(self.partition_id))
      return
    if self.part.fs_uuid is None:
      self.set_progress(999, "Partition %s on %s has no file system UUID; cannot determine mount point." % (str(self.partition_id), self.disk.device_name))
      return
    mount_point = self.part.get_mount_point()
    self.argv = ["/bin/mount", self.part.device_name, mount_point]

    if not os.path.exists(mount_point):
      try:
        os.makedirs(mount_point)
      except Exception as exc:
        self.set_progress(999, "Creating mount point failed. ")
        self.verdict.append(traceback.format_exc())
        pass
      pass
    super().setup()
    pass

  def teardown(self):
    self.part.mounted = self.progress == 100
    if self.part.mounted and self.add_mount_point != None:
      self.add_mount_point(self.disk, self.part)
      pass
    super().teardown()
    pass

  pass

#
# Run fsck on a partition
#
class task_fsck(op_task_process):
  #
  def __init__(self, description, disk=None, partition_id=None, payload_size=None, fix_file_system=False, **kwargs):
    self.disk = disk
    self.partition_id = partition_id
    self.payload_size = payload_size
    self.fix_file_system = fix_file_system
    speed = self.disk.estimate_speed("fsck")
    estimate_size = self.disk.get_byte_size() if self.payload_size is None else self.payload_size
    kwargs["time_estimate"] = estimate_size/speed+2

    # The command is just a placeholder. Actuall command is assembled in "setup"
    self.fsck_mode = "-y" if fix_file_system else "-p"
    super().__init__(description, argv=["/sbin/e2fsck", "-f", self.fsck_mode, disk.device_name, partition_id], encoding='iso-8859-1', **kwargs)
    # It's okay to be 0 - success or 1 - corrected
    self.good_returncode = [0, 1]
    pass

  def setup(self):
    #
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      error_message = "fsck: disk %s partition %s is not found" % (self.disk.device_name, self.partition_id)
      tlog.warning(error_message)
      self._setup_failed(error_message)
      return

    self.argv = ["/sbin/e2fsck", "-f", self.fsck_mode, part1.device_name]
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
    release.write("installer-version: %s.%s\n" % (TRIAGE_VERSION, TRIAGE_TIMESTAMP))
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
            msg = "Dir %s deleted." % path
            pass
          else:
            os.remove(path)
            msg = "File %s deleted." % path
            pass
          tlog.debug(msg)
          self.verdict.append(msg)
          pass
        except Exception as exc:
          self.verdict.append("Failed to remove %s" % path)
          self.verdict.append(str(exc))
          pass
        pass
      else:
        msg = "Path %s does not exist." % path
        tlog.info(msg)
        self.verdict.append(msg)
        pass
      pass
    pass
  pass


# Purge the /home/triage/.cache
class task_remove_triage_home_cache(task_remove_files):
    #
  def __init__(self, description, disk=None, partition_id='Linux', **kwargs):
    files = ["home/triage/.cache"]
    super().__init__(description, disk=disk, partition_id=partition_id, files=files, time_estimate=1, **kwargs)
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


# Bakes a one-shot systemd service into the captured image that grows the
# root partition and filesystem to fill whatever disk it's eventually
# booted from - a Raspberry-Pi-style first-boot resize, independent of
# wce-triage's own restore-time partitioning (restore_image_runner.py
# already sizes the partition correctly, so this is a redundant, harmless
# safety net there, and the only thing that saves you if the image is ever
# deployed by something other than wce-triage's restore flow, e.g. plain dd).
GROWFS_SCRIPT = '''#!/bin/sh
set -e
ROOTPART=$(findmnt -no SOURCE /)
DISK=/dev/$(lsblk -no pkname "$ROOTPART")
PARTNUM=$(cat /sys/class/block/$(basename "$ROOTPART")/partition)

# Relocate the GPT backup header to the true end of the disk first - after
# writing a shrunk image onto a bigger disk, the backup header is still
# where the old (smaller) disk ended, and parted's non-interactive -s mode
# can't answer the "Fix/Ignore" prompt that causes. No-op / harmless exit
# on non-GPT disks.
sgdisk -e "$DISK" || true

parted -s -a optimal "$DISK" resizepart "$PARTNUM" 100%
resize2fs "$ROOTPART"

systemctl disable wce-growfs-once.service
'''

GROWFS_SERVICE_UNIT = '''[Unit]
Description=WCE Triage: grow root partition and filesystem to fill disk (runs once)
After=local-fs.target
ConditionPathExists=/usr/local/sbin/wce-growfs-once.sh

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/wce-growfs-once.sh

[Install]
WantedBy=multi-user.target
'''


class task_install_growfs_service(op_task_python_simple):
    #
  def __init__(self, description, disk=None, partition_id='Linux', **kwargs):
    super().__init__(description, time_estimate=1, **kwargs)
    self.disk = disk
    self.partition_id = partition_id
    pass

  def run_python(self):
    part = self.disk.find_partition(self.partition_id)
    if part is None:
      self.set_progress(999, 'Partition does not exist.')
      return

    rootpath = part.get_mount_point()

    script_path = os.path.join(rootpath, "usr/local/sbin/wce-growfs-once.sh")
    with open(script_path, "w") as script_file:
      script_file.write(GROWFS_SCRIPT)
      pass
    os.chmod(script_path, 0o755)

    unit_path = os.path.join(rootpath, "etc/systemd/system/wce-growfs-once.service")
    with open(unit_path, "w") as unit_file:
      unit_file.write(GROWFS_SERVICE_UNIT)
      pass
    os.chmod(unit_path, 0o644)

    # Offline equivalent of "systemctl enable wce-growfs-once.service" -
    # no live systemd/chroot available while the partition is just mounted.
    wants_dir = os.path.join(rootpath, "etc/systemd/system/multi-user.target.wants")
    if not os.path.exists(wants_dir):
      os.makedirs(wants_dir)
      pass
    symlink_path = os.path.join(wants_dir, "wce-growfs-once.service")
    if os.path.islink(symlink_path) or os.path.exists(symlink_path):
      os.remove(symlink_path)
      pass
    os.symlink("../wce-growfs-once.service", symlink_path)

    self.verdict.append("Installed first-boot grow-partition service.")
    self.set_progress(100, "First-boot grow-partition service installed")
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

    if self.process.returncode:
      print("retcode = %d" % self.process.returncode)
      pass

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
  """refreshes (reads) partitions from disk.

  Deliberately avoids blkid: libblkid can report an "ambivalent result" for
  a partition carrying leftover signatures from a disk's previous partition
  layout and silently return nothing for a partition that is, in fact, a
  perfectly valid file system (confirmed on the affected box with
  dumpe2fs/file -sL). PARTUUID/PARTNAME (blkid's PARTLABEL) are read straight
  from the kernel's own GPT parse via sysfs, no subprocess involved. The file
  system UUID still needs `file -sL`, since the kernel doesn't parse
  ext4/vfat superblocks at the block layer.
  """

  uuid_re = re.compile(r'UUID=([0-9a-fA-F-]+)')
  fat_serial_re = re.compile(r'serial number (0x[0-9a-fA-F]+)')

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
      debug_msg = ["Refresh partition"]

      for part in self.disk.partitions:
        self.verdict.append("Partition %d %s (%s) - UUID %s." % (part.partition_number, part.file_system, part.partition_name, part.fs_uuid))
        debug_msg.append("Partition %d %s (%s) - UUID %s." % (part.partition_number, part.file_system, part.partition_name, part.fs_uuid))
        pass
      tlog.info("\n".join(debug_msg))
      return

    part = self.disk.partitions[self.step]
    self.step += 1

    self._read_partition_table_info(part)
    self._read_file_system_uuid(part)

    tlog.info("Partition %d %s (%s) - UUID %s." % (part.partition_number, part.file_system, part.partition_name, part.fs_uuid))

    if part.is_file_system('ext4'):
      self.ext4_count += 1
      # If this is the first linux ext4 partition, and has no name, name it 'Linux'
      if not part.partition_name and self.ext4_count == 1:
        part.partition_name = 'Linux'
        pass
      pass
    pass

  def _read_partition_table_info(self, part):
    """PARTUUID/PARTNAME straight from the kernel's own GPT parse - plain
    file read, no subprocess, no blkid."""
    uevent_path = "/sys/class/block/%s/uevent" % os.path.basename(part.device_name)
    try:
      with open(uevent_path) as f:
        for line in f:
          key, _, value = line.strip().partition('=')
          if key == 'PARTUUID':
            part.partition_uuid = value
          elif key == 'PARTNAME' and value:
            part.partition_name = value
            pass
          pass
        pass
      pass
    except OSError as exc:
      tlog.info("No sysfs uevent for %s: %s" % (part.device_name, exc))
      pass
    pass

  def _read_file_system_uuid(self, part):
    """The kernel doesn't parse file system superblocks at the block layer,
    so this is the one place we still run a command. `file -sL` reads the
    actual superblock directly, instead of blkid's PT/superblock
    cross-checking (which can spuriously report "ambivalent result")."""
    result = subprocess.run(['file', '-sL', part.device_name],
                             timeout=10, encoding=self.encoding,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = result.stdout or ""

    m = self.uuid_re.search(out)
    if m:
      part.fs_uuid = m.group(1)
      return

    m = self.fat_serial_re.search(out)
    if m:
      hexval = "%08X" % int(m.group(1), 16)
      part.fs_uuid = "%s-%s" % (hexval[:4], hexval[4:])
      pass
    pass

  def _estimate_progress(self, total_seconds):
    return int(99 / len(self.disk.partitions) * self.step)

  pass

#
#
#
class task_set_ext_partition_uuid(op_task_process_simple):
  def __init__(self, description, disk=None, partition_id=None, allow_fail=False, **kwargs):
    self.disk = disk
    self.partition_id = partition_id
    self.allow_fail = allow_fail

    kwargs["time_estimate"] = kwargs.get("time_estimate", 3)
    # argv is a placeholder
    super().__init__(description, encoding='iso-8859-1', argv=["tune2fs", "-f", "-U", disk.device_name, partition_id], **kwargs)
    pass
  
  def setup(self):
    #
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      self.set_progress(999, "Partition %s does not exist on %s" % (self.partition_id, self.disk.device_name))
      return
    if part1.fs_uuid is None:
      msg = "Partition %s on %s has no file system UUID to restore." % (self.partition_id, self.disk.device_name)
      self.set_progress(100 if self.allow_fail else 999, msg)
      return
    self.argv = ["tune2fs", "-f", "-U", part1.fs_uuid, part1.device_name]
    super().setup()
    return

  def is_success(self) -> Optional[bool]:
    if self.process.returncode is None:
      return None
    return self.allow_fail or (self.process.returncode in self.good_returncode)

  pass


#
class task_set_fat_label(op_task_process_simple):
  def __init__(self, description, disk=None, partition_id=None, **kwargs):
    self.disk = disk
    self.partition_id = partition_id
    kwargs["time_estimate"] = kwargs.get("time_estimate", 6)
    super().__init__(description, encoding='iso-8859-1', time_estimate=3, argv=["fatlabel", disk.device_name, partition_id], **kwargs)
    pass
  
  def setup(self):
    #
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      self.set_progress(999, "Partition %s does not exist on %s" % (self.partition_id, self.disk.device_name))
      return
    self.argv = ["fatlabel", part1.device_name, part1.partition_id]
    super().setup()
    return

  pass


#
class task_set_fat_volume_id(op_task_python_simple):
  """sets the FAT32's volume ID.
  There is no utility to do this so the python goes after the partition device file and writes out the ID.
  see: https://superuser.com/questions/1247972/change-uuid-of-vfat-partition
  """
  def __init__(self, description, disk=None, partition_id=None, **kwargs):
    self.disk = disk
    self.partition_id = partition_id
    super().__init__(description, time_estimate=2, **kwargs)
    pass
  
  def setup(self):
    #
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      self.set_progress(999, "Partition %s does not exist on %s" % (self.partition_id, self.disk.device_name))
      return
    super().setup()
    return

  def run_python(self):
    #
    part1 = self.disk.find_partition(self.partition_id)
    if part1 is None:
      self.set_progress(999, "Partition %s does not exist on %s" % (self.partition_id, self.disk.device_name))
      return

    device_name = self.disk.get_partition_device_file(part1.partition_number)

    if part1.file_system not in [ "fat32", "vfat" ]:
      self.set_progress(999, "Partition %s is not fat32. (%s)" % (device_name, part1.file_system))
      return

    sanity_check = re.match('[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}', part1.fs_uuid)
    if not sanity_check:
      self.set_progress(999, "Partition %s - ID %s is not for fat32" % (device_name, part1.fs_uuid))
      return
      
    hex_str = part1.fs_uuid[:4] + part1.fs_uuid[5:]
    id = struct.pack("<I", int(hex_str, 16))

    is_healthy = True
    try:
      device_file = open(device_name, "rb")
      # https://docs.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2003/cc776720(v=ws.10)?redirectedfrom=MSDN#w2k3tr_fat_how_gkxz
      # Extended BPB Fields for FAT32 Volumes
      device_file.seek(0x43)
      device_file.read(4)
      device_file.close()
    except Exception as exc:
      is_healthy = False
      msg = "Failed during attempting to read from byte 67 to 71.\n" + str(exc)
      self.verdict.append(msg)
      tlog.info(msg)
      pass

    if is_healthy:
      try:
        device_file = open(device_name, "wb")
        # https://docs.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2003/cc776720(v=ws.10)?redirectedfrom=MSDN#w2k3tr_fat_how_gkxz
        # Extended BPB Fields for FAT32 Volumes
        device_file.seek(0x43)
        device_file.write(id)
        device_file.close()
      except Exception as exc:
        is_healthy = False
        msg = "Failed during attempting to write from byte 67 to 71.\n" + str(exc)
        self.verdict.append(msg)
        tlog.info(msg)
        pass
      pass

    if is_healthy:
      msg = "FAT volume id - wrote %08x to %s" % (struct.unpack("<I", id)[0], device_name)
      self.verdict.append(msg)
      tlog.debug(msg)
      pass
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

  def __init__(self, description, disk=None, detected_videos=None, partition_id='Linux',
               universal_boot=False, bootloader_id='ubuntu', **kwargs):
    # Disk to bless
    self.disk = disk
    self.partition_id = partition_id
    (self.n_nvidia, self.n_ati, self.n_vga) = detected_videos
    self.linuxpart = None
    self.mount_dir = None
    self.efi_part = None
    self.efi_mount_dir = "/boot/efi" # relative location - not used
    self.script_path = None
    self.script = None
    self.universal_boot = universal_boot
    # Directory name grub-install creates under EFI/ (--bootloader-id).
    # Note this does NOT change the prefix baked into grubx64.efi itself -
    # on Ubuntu with shim-signed installed, grub-install copies Canonical's
    # pre-signed image, which always looks for /EFI/ubuntu/grub.cfg
    # regardless of --bootloader-id. See task_finalize_efi.
    self.bootloader_id = bootloader_id

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

    # EFI should be there.
    self.efi_part = self.disk.find_partition(EFI_NAME)

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

    # MBR Boot
    self.script.append("/usr/sbin/grub-install -v --target=i386-pc --force %s" % self.disk.device_name)

    # EFI Boot
    if self.efi_part:
      self.script.append("mkdir -p /boot/efi")
      self.script.append("chmod 700 /boot/efi")
      self.script.append("mount %s /boot/efi" % self.efi_part.device_name)

      if self.universal_boot:
        # --removable installs GRUB to the fallback place (EFI/BOOT), not the
        # bootloader-id directory below, and thus no reason to update NVRam
        grub_efi_cmd = "/usr/sbin/grub-install --target=x86_64-efi --efi-directory=/boot/efi --boot-directory=/boot --removable --no-nvram --force --recheck %s"
        self.script.append(grub_efi_cmd % (self.disk.device_name))

      # Always install into EFI/ubuntu, whatever self.bootloader_id says.
      # On Ubuntu with shim-signed installed, grub-install just copies
      # Canonical's pre-signed grubx64.efi rather than rebuilding one - that
      # binary always looks for /EFI/ubuntu/grub.cfg regardless of
      # --bootloader-id, so EFI/ubuntu has to physically exist with real
      # shim/grub/mm files no matter what directory name we'd rather use.
      grub_efi_cmd = "/usr/sbin/grub-install --target=x86_64-efi --efi-directory=/boot/efi --boot-directory=/boot --bootloader-id=ubuntu --force %s"
      self.script.append(grub_efi_cmd % (self.disk.device_name))

      if self.bootloader_id != "ubuntu":
        # Also install a second, identically-signed copy into the branded
        # directory, purely so the ESP looks self-consistent to anyone
        # browsing it. Not what grub actually reads at boot - EFI/ubuntu above is.
        grub_efi_cmd = "/usr/sbin/grub-install --target=x86_64-efi --efi-directory=/boot/efi --boot-directory=/boot --bootloader-id=%s --force %s"
        self.script.append(grub_efi_cmd % (self.bootloader_id, self.disk.device_name))
        pass

    if (not self.universal_boot) and self.n_ati > 0:
      self.script.append('# If this machine has ATI video, get rid of other video drivers that can get in its way.')
      self.script.append("apt-get -q -y --force-yes purge `dpkg --get-selections | cut -f 1 | grep -v xorg | grep nvidia-`")
      pass

    self.script.append('# Set up the grub.cfg')
    self.script.append('chmod +rw /boot/grub/grub.cfg')
    self.script.append('grub-mkconfig -o /boot/grub/grub.cfg')

    self.script.append('# clean up')
    if self.efi_part:
      self.script.append("umount /boot/efi")
    self.script.append('umount /proc || umount -lf /proc')
    self.script.append('umount /sys')
    self.script.append('umount /dev/pts')
    self.script.append('# script end')

    # Write out the bless script
    script_file = open(self.script_path, "w")
    script_text = "\n".join(self.script)
    script_file.write(script_text)
    script_file.close()
    os.chmod(self.script_path, 0o755)

    self.verdict.append("Running following script with chroot\n%s\n" % script_text)

    # Set up the /dev for chroot
    cmd = "mount --bind /dev/ %s/dev" % self.mount_dir
    subprocess.run(cmd, shell=True)
    self.verdict.append(cmd)

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
    cmd = "umount %s/dev" % self.mount_dir
    subprocess.run(cmd, shell=True)
    if self.script_path:
      try:
        os.unlink(self.script_path)
      except Exception as exc:
        self.verdict.append("Failed: " + cmd)
        self.verdict.append(str(exc))
        pass
      pass

    bless_log=open("/tmp/bless.log", "w")
    if self.out:
      msg = "stdout: \n" + self.out
      self.verdict.append(msg)
      bless_log.write(msg)
      pass
    
    if self.err:
      msg = "stderr: \n" + self.err
      self.verdict.append(msg)
      bless_log.write(msg)
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
efi_template = """# /boot/efi was on boot disk during installation
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
  def __init__(self, description, disk=None, newhostname=None, partition_id='Linux', efi_id = None, wce_share_url=None, cmdline=None, **kwargs):
    super().__init__(description, time_estimate=1, **kwargs)
    self.newhostname = newhostname
    self.disk = disk
    self.partition_id = partition_id
    self.efi_id = efi_id
    self.efi_part = None
    self.swappart = None
    self.mount_dir = None
    self.wce_share_url = wce_share_url
    self.cmdline = cmdline
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
    self.swappart = self.disk.find_partition_by_file_system("swap")
    self.mount_dir = self.linuxpart.get_mount_point()

    # patch up the restore
    fstab = open("%s/etc/fstab" % self.mount_dir, "w")
    fstab.write(fstab_template % (self.linuxpart.fs_uuid))
    if self.efi_part:
      tlog.info("fstab: EFI %s" % self.efi_part.fs_uuid)
      fstab.write(efi_template % self.efi_part.fs_uuid)
      pass
    if self.swappart:
      tlog.info("fstab: Swap %s" % self.swappart.fs_uuid)
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
      self.verdict.append("Hostname in %s/etc is updated with %s." % (self.mount_dir, self.newhostname))
      pass

    # Set the wce_share_url to /etc/default/grub
    grub_filename = "%s/etc/default/grub" % self.mount_dir
    grub_file = grub_config(grub_filename)
    grub_file.open()

    if self.wce_share_url is not None:
      grub_file.set_cmdline_option(const.wce_share, self.wce_share_url)
      pass

    # cmdline
    if self.cmdline:
      for tag, value in self.cmdline.items():
        grub_file.set_cmdline_option(tag, value)
        pass
      pass

    updated, new_grub = grub_file.generate()
    if updated:
      with open(grub_filename, "w") as grub_fd:
        grub_fd.write(new_grub)
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


    #
    # Remove /swapfile
    # 
    for removing in ["%s/swapfile"]:
      try:
        os.unlink( removing % self.mount_dir)
      except:
        # No big deal if the file isn't there or failed to remove.
        pass
      pass
    pass

  pass


# class task_finalize_disk_aux(op_task_python):
#   def __init__(self, description, disk=None, newhostname=None, partition_id='Linux', **kwargs):
#     super().__init__(description, time_estimate=1, **kwargs)
#     self.disk = disk
#     self.partition_id = partition_id
#     self.newhostname = newhostname
#     pass
#
#   def run_python(self):
#     #
#     # Patch up the grub.cfg just in case the "/dev/disk/by-uuid/%s" %
#     # self.uuid1 does not exist. If that happens, grub-mkconfig
#     # genertes the device name based grub.cfg which is bad.
#     #
#     # This should fix up the most of unbootable disk imaging.
#     #
#     part1 = self.disk.find_partition(self.partition_id)
#     root_fs = "UUID=%s" % part1.uuid
#     linux_re = re.compile(r'(\s+linux\s+[^ ]+\s+root=)([^ ]+)(\s+ro .*)')
#     grub_cfg_file = open("%s/boot/grub/grub.cfg" % self.disk.mount_dir)
#     grub_cfg = grub_cfg_file.readlines()
#     grub_cfg_file.close()
#     grub_cfg_file = open("%s/boot/grub/grub.cfg" % self.disk.mount_dir, "w")
#     for line in grub_cfg:
#       m = linux_re.match(line)
#       if m:
#         grub_cfg_file.write("%s%s%s\n" % (m.group(1), root_fs, m.group(3)))
#       else:
#         grub_cfg_file.write(line)
#         pass
#       pass
#     grub_cfg_file.close()
#     pass
#   pass

#
# Adjust grub in EFI 
#
EFI_ubuntu_grub_template = """search.fs_uuid {Linux_UUID} root hd0,gpt{Linux_part_no} 
set prefix=($root)'/boot/grub'
configfile $prefix/grub.cfg
"""

class task_finalize_efi(op_task_python_simple):
  """Rewrites the grub.cfg search-and-handoff stub with this disk's actual
  ext4 partition UUID - the UUID is freshly randomized per restore (see
  task_set_ext_partition_uuid), so whatever was baked into the source image
  is necessarily wrong for this specific disk.

  Two different builds put that stub in two different places, and which
  one a given disk has depends on which EFI image it was restored from:
  - Triage's ISO-style EFI/BOOT layout (see [[project_efi_fallback_boot_chain]]):
    a self-contained grub with prefix=/boot/grub, no /EFI/ubuntu dependency.
    The stub ships pre-baked at the ESP root, <efi>/boot/grub/grub.cfg,
    with a placeholder UUID that just needs correcting.
  - grub-install's Canonical pre-signed-image layout: creates <efi>/EFI/ubuntu/
    (shim/grub/mm) but never writes a grub.cfg of its own - this task is the
    only thing that ever does, the first time, right after task_install_grub.

  Rather than needing the caller to know in advance which kind of build this
  is (which really just depends on what the source image happened to ship),
  check for both and update whichever is actually present. They're tiny
  text files - writing both when both happen to exist is harmless.
  """
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

    efi_grub_cfg = EFI_ubuntu_grub_template.format(Linux_UUID=self.linuxpart.fs_uuid, Linux_part_no=self.linuxpart.partition_number)

    wrote_any = False

    # Triage's ISO-style stub: ships pre-baked as a real file, just needs
    # its UUID corrected for this disk.
    triage_stub_path = os.path.join(self.efi_dir, "boot", "grub", "grub.cfg")
    if os.path.isfile(triage_stub_path):
      wrote_any = self._write_grub_cfg(triage_stub_path, efi_grub_cfg) or wrote_any
      pass

    # grub-install's layout: the EFI/ubuntu/ directory exists (grub-install
    # just ran, earlier in this same restore) but grub.cfg inside it doesn't
    # yet - this is what creates it, the first time, every time.
    ubuntu_stub_path = os.path.join(self.efi_dir, "EFI", "ubuntu", "grub.cfg")
    if os.path.isdir(os.path.dirname(ubuntu_stub_path)):
      wrote_any = self._write_grub_cfg(ubuntu_stub_path, efi_grub_cfg) or wrote_any
      pass

    if not wrote_any:
      msg = ("Neither %s exists nor %s's directory exists; grub-install or the "
             "EFI image restore must run before finalizing EFI." % (triage_stub_path, ubuntu_stub_path))
      self.verdict.append(msg)
      tlog.warning(msg)
      pass
    pass

  def _write_grub_cfg(self, efi_grub_cfg_path, efi_grub_cfg):
    with open(efi_grub_cfg_path, "w") as efi_grub_cfg_fd:
      efi_grub_cfg_fd.write(efi_grub_cfg)
      pass
    self.verdict.append("%s:\n%s" % (efi_grub_cfg_path, efi_grub_cfg))
    return True
  pass


class task_setup_efi_boot_entry(op_task_process_simple):
  """Registers a persisted UEFI NVRAM boot entry (via efibootmgr) that
  points directly at the installed shim's file path, e.g.
  \\EFI\\ubuntu\\shimx64.efi.

  Why: some firmware's handling of a brand new disk - one with no NVRAM
  entry yet, so it falls back to a bare device-path boot entry - can fail
  outright on certain USB bridge chip/firmware combinations (confirmed:
  HP + Realtek RTL9210B-CG causes a "System Reset" every time, regardless
  of what file is actually at EFI/BOOT/BOOTX64.EFI), while an explicit
  file-path entry - or the firmware's own "Boot from File" browser -
  boots the exact same files fine. This task pre-creates that explicit
  entry so a fresh install doesn't need a technician to do it by hand.

  Only meaningful when the target disk is the same machine's own fixed
  controller (SATA/NVMe on the motherboard): efibootmgr computes the
  device path from the live PCI/ACPI topology of whatever disk it's
  pointed at. That's stable across reboots for a fixed internal disk
  (motherboard routing doesn't change based on what's plugged into USB
  at the time), but is *not* portable if the target disk is itself
  removable and might later be moved to different hardware or a
  different port - so this skips itself (via _noop()) for anything
  behind a USB bridge, for a missing EFI partition, or if efibootmgr
  isn't even installed.

  A real efibootmgr failure is also treated as non-fatal (is_success()
  override below) rather than left to op_task_process's default - a
  failing task here would otherwise flip the whole runner to
  RunState.Failed and abort every task after it (see runner.py's
  `if task.progress > 100`), which is exactly backwards for something
  that's explicitly a nice-to-have: worst case, the target just falls
  back to firmware's own default boot resolution, same as if this task
  didn't exist at all.
  """
  def __init__(self, description, disk=None, partition_id='Linux', efi_id=EFI_NAME, bootloader_id='ubuntu', label='Linux', **kwargs):
    self.disk = disk
    self.partition_id = partition_id
    self.efi_id = efi_id
    self.bootloader_id = bootloader_id
    self.label = label
    # Placeholder for preflight's explain() - setup() below resolves the
    # real partition number (and may skip the process entirely).
    argv = ["efibootmgr", "-c", "-d", disk.device_name, "-p", str(efi_id),
            "-L", label, "-l", "\\EFI\\%s\\shimx64.efi" % bootloader_id]
    super().__init__(description, argv=argv, time_estimate=2, **kwargs)
    pass

  def setup(self):
    if self.disk.usb_driver is not None:
      msg = ("%s is behind a USB bridge (driver: %s) - skipping efibootmgr boot "
             "entry, its device path would not survive being moved to different "
             "hardware or a different port." % (self.disk.device_name, self.disk.usb_driver))
      self.verdict.append(msg)
      tlog.info(msg)
      self._noop()
      return

    self.efi_part = self.disk.find_partition(self.efi_id)
    if self.efi_part is None:
      msg = "EFI partition %s does not exist on %s; cannot set up boot entry." % (str(self.efi_id), self.disk.device_name)
      self.verdict.append(msg)
      tlog.warning(msg)
      self._noop()
      return

    efibootmgr_path = shutil.which("efibootmgr")
    if efibootmgr_path is None:
      msg = "efibootmgr is not installed - skipping EFI boot entry setup."
      self.verdict.append(msg)
      tlog.warning(msg)
      self._noop()
      return

    self.argv = [efibootmgr_path, "-c",
                 "-d", self.disk.device_name,
                 "-p", str(self.efi_part.partition_number),
                 "-L", self.label,
                 "-l", "\\EFI\\%s\\shimx64.efi" % self.bootloader_id]
    super().setup()
    pass

  def is_success(self):
    real_success = super().is_success()
    if real_success is False:
      msg = "efibootmgr exited %d - continuing anyway, this step is optional." % self.process.returncode
      self.verdict.append(msg)
      tlog.warning(msg)
      return True
    return real_success
  pass

#
#
#
class task_mount_nfs_destination(op_task_process):
  nfs_server = None

  def __init__(self, description, **kwargs):
    super().__init__(description, **kwargs)
    pass
  
  def setup(self):
    connected = False
    for netdev in detect_net_devices():
      if netdev.is_network_connected():
        connected = True
        break
      pass
    if not connected:
      self.set_progress(999, "Network is not working.")
      return
    
    if self.nfs_server is None:
      self.nfs_server = get_router_ip_address()
      pass

    if not self.nfs_server:
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

    self.argv = [ "mount", "-t", "nfs",  "%s:/var/www" % self.nfs_server, "/mnt/www"]
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
    argv = [sys.executable, "-m", "wce_triage.bin.multiwipe"]

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

    # what's coming out from multiwipe is NDJSON: {"event": "zerowipe", "message": ProgressReport}
    lines, self.err = split_lines(self.err)
    for line in lines:
      if not line:
        continue
      try:
        report = ProgressEnvelope.model_validate_json(line).message
        self.set_progress(report.progress, report.runMessage)
        self.time_estimate = report.runEstimate
        pass
      except Exception as exc:
        msg = "bad wipe ouptut? " + traceback.format_exc() + "\n" + line
        self.verdict.append(msg)
        tlog.info(msg)
        pass
      pass

    out_lines, self.out = split_lines(self.out)
    for line in out_lines:
      self.verdict.append(line)
      pass
    pass
  pass


#
# Wipes several disks in parallel with a single bin/multiwipe.py process
# (same process that op_task_wipe_disk drives for one disk), and reports
# one TaskStatus per disk via describe_subtasks() so the Runner-level
# "tasks" list can show per-disk progress even though it's all one op_task.
#
class task_multiwipe(op_task_process):
  def __init__(self, description, devices=None, short=False, disks=None, **kwargs):
    self.devices = devices or []
    self.short = short
    self.device_reports = {}

    argv = [sys.executable, "-m", "wce_triage.bin.multiwipe"]
    if short:
      argv.append("-s")
      pass
    argv = argv + self.devices

    estimate = 2
    if not short and disks:
      estimate += sum(disk.get_byte_size() for disk in disks) / 40000000
      pass
    kwargs["time_estimate"] = kwargs.get("time_estimate", estimate)
    super().__init__(description, argv=argv, **kwargs)
    pass

  def poll(self):
    super().poll()
    self._parse_wipe_progress()
    self._update_aggregate_progress()
    pass

  def _parse_wipe_progress(self):
    if len(self.err) == 0:
      return

    lines, self.err = split_lines(self.err)
    for line in lines:
      if not line:
        continue
      try:
        report = ProgressEnvelope.model_validate_json(line).message
        self.device_reports[report.key] = report
        pass
      except Exception as exc:
        msg = "bad wipe ouptut? " + traceback.format_exc() + "\n" + line
        self.verdict.append(msg)
        tlog.info(msg)
        pass
      pass

    out_lines, self.out = split_lines(self.out)
    for line in out_lines:
      self.verdict.append(line)
      pass
    pass

  def _update_aggregate_progress(self):
    # bin/multiwipe.py always exits 0 once every wiper thread stops, whether
    # or not a given disk actually finished - so completion/failure has to be
    # read from the per-disk reports, not the process return code.
    if not self.device_reports:
      return

    progresses = {key: report.progress for key, report in self.device_reports.items()}
    heard_from_all = len(self.device_reports) >= len(self.devices)

    failed = [key for key, progress in progresses.items() if progress == 999]
    if failed:
      self.set_progress(999, "Failed to wipe: %s" % ", ".join(failed))
      return

    if heard_from_all and all(progress == 100 for progress in progresses.values()):
      self.set_progress(100, "All disks wiped.")
      return

    still_running = [progress for progress in progresses.values() if progress < 100]
    overall = min(still_running) if still_running else 99
    self.set_progress(overall, "Wiping %d of %d disks." % (len(still_running), len(self.devices)))
    estimates = [report.runEstimate for report in self.device_reports.values() if report.runEstimate]
    if estimates:
      self.time_estimate = max(estimates)
      pass
    pass

  def describe_subtasks(self, current_time):
    elapsed = round(in_seconds(current_time - self.start_time), 1) if self.start_time else 0
    result = []
    for device in self.devices:
      report = self.device_reports.get(device)
      if report is None:
        result.append(TaskStatus(step=self.task_number if self.task_number is not None else 0,
                                 taskCategory="Wipe %s" % device,
                                 taskProgress=0,
                                 taskEstimate=self.time_estimate,
                                 taskElapse=elapsed,
                                 taskStatus="waiting",
                                 taskExplain="Wipe %s" % device))
        continue

      task_status = {RunState.Running: "running", RunState.Success: "done", RunState.Failed: "fail"}.get(report.runStatus, "running")
      result.append(TaskStatus(step=self.task_number if self.task_number is not None else 0,
                               taskCategory="Wipe %s" % device,
                               taskProgress=report.progress,
                               taskEstimate=report.runEstimate,
                               taskElapse=elapsed,
                               taskStatus=task_status,
                               taskMessage=report.runMessage,
                               taskExplain="Wipe %s" % device,
                               taskVerdict=[report.verdict] if report.verdict else []))
      pass
    return result

  def explain(self):
    return "Wipe disks: " + ", ".join(self.devices)

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
          tlog.debug("{part}".format(part=self.disk.get_partition_device_file(str(self.n_partitions))) + " Disks: " + ",".join([ node for node in os.listdir('/dev') if node[:2] == 'sd' or node[:4] == 'nvme']))
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
      part_device_name = self.disk.get_partition_device_file(str(part_no+1))
      if not os.path.exists(part_device_name):
        return False
      pass
    return True

  pass


class task_fs_sync(op_task_process_simple):
  """Run sync command to flush the fs cache"""

  def __init__(self, description: str, **kwargs):

    argv = ['sync']
    super().__init__(description,
                     argv=argv,
                     time_estimate=10,
                     progress_finished="File system synced",
                     **kwargs)
    pass

  pass

