#!/usr/bin/python3
import io
import os, sys, datetime, json, traceback, signal, stat
import threading
from ..lib.util import get_triage_logger
from ..lib.timeutil import in_seconds
from ..ops.run_state import RunState, RUN_STATE
import queue
import time
import multiprocessing as mp
import typing

start_time = datetime.datetime.now()
tlog = get_triage_logger()
debugging = False

def handler_stop_signals(signum, frame):
  fanout_copy.running = False
  pass


def debuglog(msg):
  if debugging:
    print(msg)
    tlog.debug(msg)
    pass
  pass

#
# Write aka consumer process
#
def writer(key, filename, pipe):
  debuglog("start {}\n".format(filename))
  try:
    os.unlink(filename)
  except:
    pass

  with open(filename, "wb") as out:
    size_written = 0
    while True:
      try:
        data = pipe.recv()
      except EOFError:
        pipe.send(None)
        break

      try:
        out.write(data)
        size_written += len(data)
        pipe.send(size_written)
        pass
      except:
        pipe.send(None)
        pipe.close()
        break
      pass
    pass
  pass


class fanout_copy:
  '''Copy a file to multiple locations. (aka duplication)
'''
  # downstreams: typing.List[ typing.Tuple(Optional[str], str, mp.connection.Connection, mp.Process) ]

  def __init__(self, source_file, destinations, output=sys.stderr):
    self.source_file_size = None
    self.source_file = source_file
    self.destination_specs = destinations
    self.output=sys.stderr
    self.downstreams = []
    self.running = True

    try:
      src_stat = os.stat(source_file)
      if not stat.S_ISREG(src_stat.st_mode):
        print("Source file '%s' is not a regular file." % source_file, file=output)
        sys.exit(1)
        pass
      source_file_size = src_stat.st_size
      pass
    except Exception as exc:
      print(traceback.format_exc())
      sys.exit(1)
      pass

    self.source_file_size = source_file_size
    self.copybuf_size = 32 * 1024 * 1024
    self.readbufs = queue.Queue()

    for dummy in range(4):
      self.readbufs.put(bytearray(self.copybuf_size))
      pass

    self.writebufs = queue.Queue()

    self.sofar = 0
    self.progress = 0
    self.report_time = None

    self.dead_child = {}
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
    self.downstreams = []
    for idx, destination in enumerate(self.destination_specs):
      dest = destination.split(':')
      key, filename = (None, dest[0]) if len(dest) == 1 else (dest[0], dest[1])
      mine, kid = mp.Pipe()
      child = mp.Process(target=writer, args=(key, filename, kid))
      child.start()
      self.downstreams.append((idx, key, filename, mine, child))
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
        self.report_read_error({"filename": self.source_file})
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

      n_alive = 0

      for idx, key, filename, pipe, child in self.downstreams:
        if self.dead_child.get(idx):
          debuglog("1: child %d dead" % idx)
          continue
        if not child.is_alive():
          debuglog("2: child %d dead" % idx)
          continue

        try:
          pipe.send(buf)
          n_alive += 1
        except:
          debuglog("Writer got an exception. " + traceback.format_exc())
          try:
            debuglog("killing %d" % idx)
            child.kill()
          except:
            debuglog("killing %d failed" % idx)
            pass
          self.dead_child[idx] = (exc.format_exc(), self.sofar)
          self.report_write_error({"filename": filename})
          pass
        pass

      self.sofar += len(buf)

      for idx, key, filename, pipe, child in self.downstreams:
        if self.dead_child.get(idx):
          continue
        if not child.is_alive():
          continue

        try:
          child_sofar = pipe.recv()
          debuglog("{} ack {}".format(idx, child_sofar))
          pass
        except Exception as exc:
          self.dead_child[idx] = (traceback.format_exc(), self.sofar)
          debuglog("Writer got an exception. " + traceback.format_exc())
          debuglog(self.dead_child)
          try:
            debuglog("killing %d" % idx)
            child.kill()
          except:
            debuglog("killing %d failed" % idx)
            pass
          self.report_write_error({"filename": filename})
          pass
        pass

      if len(buf) == self.copybuf_size:
        # If this is a real buffer, return this to the queue.
        self.readbufs.put(buf)
        pass

      self.running = (n_alive > 0)
      pass

    self._kill_all()
    pass


  def make_running_report(self, dest, current_time=None):
    if current_time is None:
      current_time = datetime.datetime.now()
      pass
    dt_elapsed = in_seconds(current_time - start_time)

    idx, key, dest_path, pipe, child = dest

    run_state = RunState.Failed if idx in self.dead_child else (RunState.Running if self.running else RunState.Success)
    debuglog("{} {}".format(idx, run_state))

    speed = self.sofar / dt_elapsed
    if speed == 0:
      speed = 2 ** 24
      pass
    bytesCopied = 0

    if run_state is RunState.Running:
      bytesCopied = self.sofar
      run_message = "Copied %d of %d bytes. (%dMB/sec)" % (self.sofar, self.source_file_size, round(speed/(2**20), 1)),
      percentage_done = float(self.sofar) / float(self.source_file_size)
      progress = min(99, max(1, round(100*percentage_done)))
      remaining_bytes = self.source_file_size - self.sofar
      time_remaining = remaining_bytes / speed
    elif run_state is RunState.Success:
      bytesCopied = self.source_file_size
      run_message = "Copying completed (%d bytes copied.)" % (self.source_file_size),
      progress = 100
      remaining_bytes = 0
      time_remaining = 0
    else:
      msg, size_failed = self.dead_child.get(idx, ("FOO", "-1"))
      bytesCopied = size_failed
      run_message = "Copying failed at %d." % size_failed
      progress = 999
      remaining_bytes = 0
      time_remaining = 0
      pass

    report = {"key": key,
              "totalBytes": bytesCopied,
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
      for downstream in self.downstreams:
        report = self.make_running_report(downstream)
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
  
  def _kill_all(self):
    for downstream in self.downstreams:
      idx, key, filename, pipe, child = downstream
      try:
        pipe.close()
        pass
      except Exception as exc:
        pass
      pass

      try:
        child.kill()
        pass
      except Exception as exc:
        pass
      pass
    pass

  def teardown(self):
    current_time = datetime.datetime.now()
    self._kill_all()

    for downstream in self.downstreams:
      report = self.make_running_report(downstream)
      idx, key, filename, pipe, child = downstream
      if idx in self.dead_child:
        verdict, size_copied = self.dead_child[idx]
        pass
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

  mp.set_start_method('fork')

  try:
    copier.run()
  except Exception as exc:
    sys.stdout.write(traceback.format_exc())
    sys.exit(1)
    pass
  pass
    
