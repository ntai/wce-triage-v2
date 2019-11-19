#!/usr/bin/python3

import os, sys, datetime, json, traceback, signal, stat
import threading
from ..lib.util import init_triage_logger
from ..lib.timeutil import in_seconds
from ..ops.run_state import RunState, RUN_STATE
import queue
import time

start_time = datetime.datetime.now()
tlog = init_triage_logger()
debugging = True

def handler_stop_signals(signum, frame):
  fanout_copy.running = False
  pass


def debuglog(msg):
  if debugging:
    print(msg)
    tlog.debug(msg)
    pass
  pass



class fanout_copy:
  '''Copy a file to multiple locations. (aka duplication)
'''
  running = True


  def __init__(self, source_file, destinations, output=sys.stderr):
    self.source_file_size = None
    self.source_file = source_file
    self.destination_specs = destinations
    self.destinations = []
    self.output=sys.stderr

    try:
      src_stat = os.stat(source_file)
      if not stat.S_ISREG(src_stat.st_mode):
        print("Source file '%s' is not a regular file." % source_file, file=output)
        sys.exit(1)
        pass
      source_file_size = src_stat.st_size;
      pass
    except Exception as exc:
      print(traceback.format_exc())
      sys.exit(1)
      pass

    self.source_file_size = source_file_size

    self.destinations = []

    self.copybuf_size = 32 * 1024 * 1024
    self.readbufs = queue.Queue()

    for dummy in range(4):
      self.readbufs.put(bytearray(self.copybuf_size))
      pass

    self.writebufs = queue.Queue()

    self.sofar = 0
    self.progress = 0
    self.report_time = None

    self.invalid_fds = {}
    pass


  def run(self):
    self.open_source()
    self.open_destinations()
    self.copy()
    self.teardown()
    pass
  

  def open_source(self):
    try:
      self.source_fd = open(self.source_file, "rb", buffering=0)
    except Exception as exc:
      print(traceback.format_exc())
      sys.exit(1)
      pass
    pass

  def open_destinations(self):
    destinations = [ (d[0], d[1]) if len(d) == 2 else (None, d[0]) for d in [dest.split(':') for dest in self.destination_specs] ]
    # This is for cleaning up when something goes wrong.
    dest_files = []

    for key, dest_path in destinations:
      try:
        self.destinations.append((open(dest_path, 'wb', buffering=0), dest_path, key))
        dest_files.append(dest_path)
        debuglog("Dest file %s on %s opened" % (dest_path, key))
      except Exception as exc:
        # Clean up the mess if I can.
        for dest_file in dest_files:
          try:
            os.unlink(dest_file)
          except:
            pass
          pass
        tlog.info("Opening desination file %s failed with following error.\%s" (dest_path, traceback.format_exc()))
        sys.exit(1)
        pass
      pass
    pass


  def _report(self, report, current_time = None):
    if current_time is None:
      current_time = datetime.datetime.now()
      pass
    dt_elapsed = in_seconds(current_time - start_time)
    report["startTime"] = start_time.isoformat()
    report["currentTime"] = current_time.isoformat()
    report["runTime"] = (in_seconds(dt_elapsed))
    print(json.dumps(report), file=self.output, flush=True)
    pass
  

  def _report_error(self, report, **kwargs):
    report["runStatus"] = RUN_STATE[RunState.Failed.value]
    report["runEstimate"] = 0
    report["totalBytes"] = 0
    report["remainingBytes"] = 0
    report["timeReamining"] = 0
    report["progress"] = 999
    self._report(report, **kwargs)
    pass

  def report_read_error(self, report, **kwargs):
    report["runMessage"] = "Read failed. %d of %d bytes copied." % (self.sofar, self.source_file_size)
    self._report_error(report, **kwargs)
    pass


  def report_write_error(self, report, **kwargs):
    report["runMessage"] = "Write failed. %d of %d bytes copied." % (self.sofar, self.source_file_size)
    self._report_error(report, **kwargs)
    pass


  def reader(self):
    read_remaining = self.source_file_size
    copybuf_size = self.copybuf_size
    while self.running and read_remaining > 0:
      copy_size = copybuf_size if read_remaining >= copybuf_size else read_remaining

      copybuf = self.readbufs.get()
      try:
        bytesread = self.source_fd.readinto(copybuf)
        read_remaining -= bytesread
        if copy_size == copybuf_size:
          valid_data = copybuf
        else:
          # This must be the last read
          valid_data = copybuf[:bytesread]
          self.readbufs.put(copybuf)
          pass
        self.writebufs.put(valid_data)
      except Exception as exc:
        debuglog("Reader got an exception. " + traceback.format_exc())
        self.running = False
        self.report_read_error()
        continue
      pass
    self.writebufs.put(None)
    debuglog("Reader sent EOF.")
    self.source_fd.close()
    pass


  def writer(self):
    self.sofar = 0
    self.write_start_time = datetime.datetime.now()
    
    while self.running and self.source_file_size > self.sofar:
      buf = self.writebufs.get()
      if buf is None:
        break

      for dest_fd, dest_path, key in self.destinations:
        if dest_fd in self.invalid_fds:
          continue

        try:
          dest_fd.write(buf)
        except Exception as exc:
          debuglog("Writer got an exception. " + traceback.format_exc())
          self.invalid_fds[dest_fd] = (exc.format_exc(), self.sofar)
          self.report_write_error(dest_fd)
          dest_fd.close()
          pass
        finally:
          pass
        pass

      self.sofar += len(buf)

      if len(buf) == self.copybuf_size:
        # If this is a real buffer, return this to the queue.
        self.readbufs.put(buf)
        pass
      pass

    for dest_fd, dest_path, key in self.destinations:
      if dest_fd in self.invalid_fds:
        continue
      dest_fd.close()
      pass
    pass


  def make_running_report(self, dest, current_time=None):
    if current_time is None:
      current_time = datetime.datetime.now()
      pass
    dt_elapsed = in_seconds(current_time - start_time)

    dest_fd, dest_path, key = dest

    run_state = RunState.Failed if dest_fd in self.invalid_fds else (RunState.Running if self.running else RunState.Success)

    speed = self.sofar / dt_elapsed
    if speed == 0:
      speed = 2 ** 24
      pass

    if run_state is RunState.Running:
      run_message = "Copied %d of %d bytes. (%dMB/sec)" % (self.sofar, self.source_file_size, round(speed/2*20, 1)),
      percentage_done = float(self.sofar) / float(self.source_file_size)
      progress = min(99, max(1, round(100*percentage_done)))
      remaining_bytes = self.source_file_size - self.sofar
      time_remaining = remaining_bytes / speed
    elif run_state is RunState.Success:
      run_message = "Copying completed (%d bytes copied.)" % (self.source_file_size),
      progress = 100
      remaining_bytes = 0
      time_remaining = 0
    else:
      msg, size_failed = self.invalid_fds[dest_fd]
      run_message = "Copying failed at %d." % size_failed
      progress = 999
      remaining_bytes = 0
      time_remaining = 0
      pass


    report = {"key": key,
              "destination": dest_path,
              "runStatus": RUN_STATE[run_state.value],
              "runMessage": run_message,
              "progress": progress,
              "remainingBytes": remaining_bytes,
              "runEstimate" : round(time_remaining+in_seconds(dt_elapsed))
    }
    return report
  
    
  def reporter(self):
    while self.running:
      for destination in self.destinations:
        report = self.make_running_report(destination)
        self._report(report)
        pass
      time.sleep(1)
      pass
    pass


  def copy(self):
    debuglog("Copy started.")
    signal.signal(signal.SIGINT, handler_stop_signals)
    # signal.signal(signal.SIGTERM, handler_stop_signals)

    self.writer = threading.Thread(target=self.writer, args=())
    self.writer.start()
    debuglog("Writer started.")

    self.reader = threading.Thread(target=self.reader, args=())
    self.reader.start()
    debuglog("Reader started.")

    self.reporter = threading.Thread(target=self.reporter, args=())
    self.reporter.start()
    debuglog("Reporter started.")
    
    self.reader.join()
    debuglog("Reader finished.")

    self.writer.join()
    debuglog("Writer finished.")

    self.running = False
    self.reporter.join()
    pass
  
  def teardown(self):
    current_time = datetime.datetime.now()

    for destination in self.destinations:
      dest_fd, dest_path, key = destination
      try:
        dest_fd.close()
        pass
      except Exception as exc:
        pass
      pass

      report = self.make_running_report(destination)
      if dest_fd in self.invalid_fds:
        verdict, size_copied = self.invalid_fds[dest_fd]
      
      self._report(report, current_time=current_time)
      pass
    pass
  pass
  
  
if __name__ == "__main__":
  if len(sys.argv) < 2:
    usage = '''fanout_copy.py source_file destination[,destination...]
  desination:
    key:destination file path
    key is used to ID the copying file.'''
    sys.stderr.write(usage)
    sys.exit(1)
    pass
    
  source = sys.argv[1]
  dests = sys.argv[2:]
  copier = fanout_copy(source, dests)
  try:
    copier.run()
  except Exception as exc:
    sys.stdout.write(traceback.format_exc())
    sys.exit(1)
    pass
  pass
    
