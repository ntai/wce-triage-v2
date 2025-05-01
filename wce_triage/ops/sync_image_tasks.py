#
# Tasks: each task is a operation. Some tasks can take a long time.
#
# For example, a task is like mkfs. As the task runs, it should produce progress
#
# By calling into diskop, it creates the plan - which is the sequence of tasks.
# exec runs through the tasks.
#
import datetime
import os, json, traceback
import re
import sys

from ..lib import in_seconds
from ..lib.util import get_triage_logger
from .run_state import RUN_STATE, RunState
from ..lib.disk_images import list_image_files
from .tasks import op_task_process_simple

tlog = get_triage_logger()


class task_image_sync:
  """image sync task
"""
  def __init__(self, desc, **kwargs):
    self.partitions = []
    pass

  def add_mount_point(self, disk, part):
    self.partitions.append((disk, part))
    pass

  def update_time_estimate(self):
    pass

  pass


class task_image_sync_delete( op_task_process_simple, task_image_sync ):
  """delete disk image file
"""

  def __init__(self, description, keepers=None, testflight=False, **kwargs):
    if testflight:
      print("Test flight %s" % description)
      pass
    self.keepers = {}
    for keeper in keepers if keepers else []:
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
                     progress_running="Deleting disk image files",
                     progress_finished="Disk image files deleted",
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
      self.set_task_finished_message("No disk image files to delete")
      pass

    super().setup()
    pass
  pass


class task_image_sync_copy(op_task_process_simple, task_image_sync):
  """copy disk image files
"""

  def __init__(self, description, source=None, scoreboard=None, testflight=False, **kwargs):
    self.source = source if source else {}
    self.scoreboard = scoreboard if scoreboard else {}
    self.testflight = testflight
    if self.testflight:
      bin = ["echo", sys.executable]
    else:
      bin = [sys.executable]
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

  def preflight(self, tasks):
    super().preflight(tasks)
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
        self.scoreboard[disk.device_name]["total_size"] += self.source["size"]
        pass
      else:
        no_copy = {"key": disk.device_name,
                              "verdict": "No copy",
                              "runMessage": "No copy",
                              "runStatus": RunState.Success.value,
                              "totalBytes": 0,
                              "runTime": 1,
                              "runEstimate": 1,
                              "remainingBytes": 0,
                              "timeRemaining": 0,
                              "progress": 100}
        cmd = f'import sys, json; json.dump({repr(no_copy)}, sys.stderr); print("",file=sys.stderr)'
        self.argv = [sys.executable, "-c", cmd]
        pass
      pass
    super().setup()
    pass

  def poll(self):
    self._poll_process()
    self.pares_fanout_copy_progress()
    pass

  def pares_fanout_copy_progress(self):
    #
    if len(self.err) == 0:
      return

    # look for a line
    last_report = None
    while True:
      newline = self.err.find('\n')
      if newline < 0:
        break
      line = self.err[:newline]
      self.err = self.err[newline+1:]
      #current_time = datetime.datetime.now()

      # each line is a json record
      try:
        report = json.loads(line)
        device_name = report['key']
        self.scoreboard[device_name]["report"] = report
        last_report = report

        if "verdict" in report:
          self.verdict.append("%s: %s" % (device_name, report["verdict"]))
          pass

        scoreboard = self.scoreboard[device_name]
        if report["runStatus"] == RUN_STATE[RunState.Running.value]:
          scoreboard["inflight_size"] = report["totalBytes"]
          scoreboard["inflight_seconds"] = report["runTime"]
        elif report["runStatus"] == RUN_STATE[RunState.Success.value]:
          scoreboard["inflight_size"] = 0
          scoreboard["inflight_seconds"] = 0

          scoreboard["completed_size"] += report["totalBytes"]
          scoreboard["completed_seconds"] += report["runTime"]
        elif report["runStatus"] == RUN_STATE[RunState.Failed.value]:
          scoreboard["inflight_size"] = 0
          scoreboard["inflight_seconds"] = report["runTime"]
          pass

        scoreboard["bps"] = 1
        #scoreboard["bps"] = (scoreboard["completed_size"] + scoreboard["inflight_size"]) / (scoreboard["completed_seconds"] + scoreboard["inflight_seconds"])
        pass
      except Exception as exc:
        msg = "Output line: '" + line + "'\n" + traceback.format_exc()
        tlog.info("Image copy: "+ msg)
        self.verdict.append(msg)
        pass
      pass

    if last_report:
      report = last_report
      self.set_progress(report['progress'], report['runMessage'])
      self.set_time_estimate(report['runEstimate'])
      pass
    pass


  def teardown(self):
    super().teardown()
    for disk, part in self.partitions:
      scoreboard = self.scoreboard[disk.device_name]
      self.verdict.append("%s: Copied %d bytes in %d seconds. Byte/sec = %d" % (disk.device_name, scoreboard["completed_size"], scoreboard["completed_seconds"], scoreboard["bps"]))
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
                     progress_running="Synching disk metadata synced for %s" % disk.device_name,
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



def time_string_to_seconds(time_str):
  parsed_time = datetime.datetime.strptime(time_str, '%H:%M:%S').time()
  total_seconds = parsed_time.hour * 3600 + parsed_time.minute * 60 + parsed_time.second
  return float(total_seconds)


class task_image_rsync(op_task_process_simple, task_image_sync):
  """
  copy disk image files using rsync
"""

  def __init__(self, description, source=None, scoreboard=None, testflight=False, **kwargs):
    self.source = source if source else {}
    self.scoreboard = scoreboard if scoreboard else {}
    self.testflight = testflight
    if self.testflight:
      bin = ["echo", sys.executable]
    else:
      bin = [sys.executable]
      pass

    source_filename = self.source["name"]
    argv = bin + ['-m', 'wce_triage.bin.rsync_copy', self.source["fullpath"]]
    super().__init__(description,
                     argv=argv,
                     progress_finished="Image file %s copied" % source_filename,
                     time_estimate=100,
                     **kwargs)
    task_image_sync.__init__(self, description)
    pass

  def preflight(self, tasks):
    tlog.info("rsync preflight")
    super().preflight(tasks)
    pass

  def setup(self):
    # First, need the list of files
    #
    tlog.info("rsync setup")
    self.start_time = datetime.datetime.now()
    self.pids = []
    self.success = None

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
        tlog.debug(f"rsync argv {self.argv!r}")
        self.scoreboard[disk.device_name]["total_size"] += self.source["size"]
        pass
      else:
        no_copy = {"key": disk.device_name,
                              "verdict": "No copy",
                              "runMessage": "No copy",
                              "runStatus": RUN_STATE[RunState.Success.value],
                              "totalBytes": 0,
                              "runTime": 1,
                              "runEstimate": 1,
                              "remainingBytes": 0,
                              "timeRemaining": 0,
                              "progress": 100}
        cmd = f'import sys, json; json.dump({repr(no_copy)}, sys.stderr); print("",file=sys.stderr)'
        self.argv = [sys.executable, "-c", cmd]
        pass
      pass
    super().setup()
    pass

  def poll(self):
    self._poll_process()
    self.parse_rsync_copy_progress()
    pass

  def parse_rsync_copy_progress(self):
    #
    if len(self.err) == 0:
      return

    # look for a line
    last_report = None
    source_size = self.source["size"]
    prefix = "RSYNC-COPY: "
    while True:
      newline = self.err.find('\n')
      if newline < 0:
        break
      line = self.err[:newline]
      self.err = self.err[newline+1:]
      current_time = datetime.datetime.now()
      device_name = ""

      # each line
      # RSYNC-COPY: devicename:./foo:.stdout:2,950,004,736   7%  703.86MB/s    0:00:48
      #  or
      # RSYNC-COPY: rsync PID=349073 retcode None
      try:
        dt_elapsed = in_seconds(current_time - self.start_time)
        report = None
        if not line.startswith(prefix):
          try:
            report = json.loads(line)
            device_name = report['key']
            self.scoreboard[device_name]["report"] = report

            if "verdict" in report:
              self.verdict.append("%s: %s" % (device_name, report["verdict"]))
              pass

            scoreboard = self.scoreboard[device_name]
            if report["runStatus"] == RUN_STATE[RunState.Running.value]:
              scoreboard["inflight_size"] = report["totalBytes"]
              scoreboard["inflight_seconds"] = report["runTime"]
            elif report["runStatus"] == RUN_STATE[RunState.Success.value]:
              scoreboard["inflight_size"] = 0
              scoreboard["inflight_seconds"] = 0

              scoreboard["completed_size"] += report["totalBytes"]
              scoreboard["completed_seconds"] += report["runTime"]
            elif report["runStatus"] == RUN_STATE[RunState.Failed.value]:
              scoreboard["inflight_size"] = 0
              scoreboard["inflight_seconds"] = report["runTime"]
              pass

            scoreboard["bps"] = 1
          except:
            pass
        else:
          line = line[len(prefix):]

          chunks = line.split(":", maxsplit=4)
          device_name = chunks[0]

          report = None

          if line.find("PID=") >= 0:
            started = re.match(r"([^\s]+) PID=(\d+) start", chunks[1])
            exited = re.match(r"([^\s]+) PID=(\d+)\s+exited with (\d+)", chunks[1])

            if exited:
              report = {
                "key": device_name,
                "runTime": dt_elapsed,
                "runEstimate": dt_elapsed
              }
              tlog.info("rsync exited")
              pid = exited.group(2)
              self.pids.remove(pid)
              tlog.info(f"rsync exited {self.pids!r}")
              if exited.group(3) == "0":
                msg = "%s: complete" % (device_name)
                self.verdict.append(msg)
                report["runStatus"] = RUN_STATE[RunState.Success.value]
                report["progress"] = 100
                report["totalBytes"] = source_size
                report["runMessage"] = msg
                if len(self.pids) == 0:
                  self.progress = 100
              else:
                msg = "%s: failed" % (device_name)
                self.verdict.append(msg)
                report["runStatus"] = RUN_STATE[RunState.Failed.value]
                report["progress"] = 999
                report["runMessage"] = msg
                self.progress = 999
                pass
              pass

            if started:
              pid = started.group(2)
              self.pids.append(pid)
              tlog.info(f"rsync start {self.pids!r}")
              report = {
                "key": device_name,
                "runTime": dt_elapsed,
                "runStatus": RUN_STATE[RunState.Running.value],
                "progress": 0,
                "runMessage": f"copy to {device_name} started",
                "totalBytes": 0,
                "runEstimate": self.time_estimate
              }
              pass
            pass
          else:
            filename = chunks[1]
            which = chunks[2]
            # pid = chunks[3]
            rsync_progress = chunks[4]
            tlog.info(f"rsync poll {chunks!r}")

            if which == ".stdout":
              progress = re.match(r"([\d,])+\s+(\d+)%\s+([^\s]+)\s+([^\s]+)", rsync_progress)
              if progress:
                tlog.info(f"rsync progress {progress!r}")
                copied = progress.group(1)
                copied_bytes = int(copied.replace(",", ""))
                percent = int(progress.group(2))
                speed = progress.group(3)
                time_remaining = progress.group(4)
                remaining_bytes = source_size - copied_bytes
                run_message = f"{filename} {copied_bytes}/{source_size} {percent}% at {speed}"
                report = {
                  "key": device_name,
                  "runTime": dt_elapsed,
                  "destination": filename,
                  "totalBytes": int(copied.replace(",", "")),
                  "runStatus": RUN_STATE[RunState.Running.value],
                  "runMessage": run_message,
                  "progress": max(0, min(99, percent)),
                  "remainingBytes": remaining_bytes,
                  "runEstimate": round(time_string_to_seconds(time_remaining) + in_seconds(dt_elapsed))
                }
                self.scoreboard[device_name]["report"] = report
                pass
              pass
            else:
              tlog.info(f"rsync ??? {chunks!r}")
            pass

        if report:
          last_report = report

          scoreboard = self.scoreboard[device_name]
          if report["runStatus"] == RUN_STATE[RunState.Running.value]:
            scoreboard["inflight_size"] = report["totalBytes"]
            scoreboard["inflight_seconds"] = report["runTime"]
          elif report["runStatus"] == RUN_STATE[RunState.Success.value]:
            scoreboard["inflight_size"] = 0
            scoreboard["inflight_seconds"] = 0

            scoreboard["completed_size"] += report["totalBytes"]
            scoreboard["completed_seconds"] += report["runTime"]
          elif report["runStatus"] == RUN_STATE[RunState.Failed.value]:
            scoreboard["inflight_size"] = 0
            scoreboard["inflight_seconds"] = report["runTime"]
            pass

          scoreboard["bps"] = 1
        #scoreboard["bps"] = (scoreboard["completed_size"] + scoreboard["inflight_size"]) / (scoreboard["completed_seconds"] + scoreboard["inflight_seconds"])
        pass
      except Exception as exc:
        msg = "Output line: '" + line + "'\n" + traceback.format_exc()
        tlog.info("Image copy: "+ msg)
        self.verdict.append(msg)
        pass
      pass

    if last_report:
      report = last_report
      self.set_progress(report['progress'], report['runMessage'])
      self.set_time_estimate(report['runEstimate'])
      pass
    pass


  def teardown(self):
    super().teardown()
    for disk, part in self.partitions:
      scoreboard = self.scoreboard[disk.device_name]
      self.verdict.append("%s: Copied %d bytes in %d seconds. Byte/sec = %d" % (disk.device_name, scoreboard["completed_size"], scoreboard["completed_seconds"], scoreboard["bps"]))
      pass
    pass

  pass
