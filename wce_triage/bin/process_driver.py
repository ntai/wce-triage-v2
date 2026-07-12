#
# Probably, I need to deal with signals. That's gonna be future project.
#
import os, sys, datetime, traceback, select
import subprocess

if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

from ..lib.util import get_triage_logger
from ..lib.timeutil import in_seconds
from ..lib.pipereader import PipeReader
from ..ops.protocol import DriverEvent, DriverEventType, emit_line
import os, signal


tlog = get_triage_logger()

from collections import namedtuple
PipeInfo = namedtuple('PipeInfo', 'app, process, pipetag, pipe')

from enum import Enum

class DriverState(Enum):
  Running = 1
  Stopping = 2
  Done = 3
  pass

def _terminate_all(processes):
  for proc_name, process in processes:
    process.terminate()
    pass
  pass


class DriverEmitter:
  """Emits process_driver's per-line events as NDJSON (DriverEvent) on stderr,
  replacing the old '<name>: <proc>.<pipetag>:<text>' plain-text framing."""

  def start(self, proc, pid):
    tlog.debug("%s PID=%d start" % (proc, pid))
    emit_line(DriverEvent(type=DriverEventType.start, proc=proc, pid=pid), stream=sys.stderr)
    pass

  def line(self, proc, stream, text):
    text = text.strip()
    if not text:
      return
    tlog.debug("%s.%s: %s" % (proc, stream, text))
    emit_line(DriverEvent(type=DriverEventType.line, proc=proc, stream=stream, line=text), stream=sys.stderr)
    pass

  def exit(self, proc, pid, returncode):
    tlog.debug("%s PID=%s exited with %s" % (proc, pid, returncode))
    emit_line(DriverEvent(type=DriverEventType.exit, proc=proc, pid=pid, returncode=returncode), stream=sys.stderr)
    pass

  def error(self, proc, text, pid=None):
    text = text.strip()
    if not text:
      return
    for one_line in text.split('\n'):
      if not one_line:
        continue
      tlog.debug("%s.ERROR: %s" % (proc, one_line))
      emit_line(DriverEvent(type=DriverEventType.error, proc=proc, pid=pid, line=one_line), stream=sys.stderr)
      pass
    pass
  pass


#
#
#
def handler_stop_signals(signum, frame):
  '''propagate terminate signal to children'''
  global all_processes
  _terminate_all(all_processes)
  pass

#
# Probably it's better to make this to a class...
#
def drive_process(name, processes, pipes, encoding='iso-8859-1', timeout=0.25):
  global all_processes
  all_processes = processes
  signal.signal(signal.SIGINT, handler_stop_signals)
  signal.signal(signal.SIGTERM, handler_stop_signals)

  #
  printer = DriverEmitter()

  for proc_name, process in processes:
    printer.start(proc_name, process.pid)
    pass
  #
  drive_process_retcode = 0

  # gatherer gathers pipe outs
  gatherer = select.poll()
  fd_map = {}
  for pipeinfo in pipes:
    fd = pipeinfo.pipe.fileno()
    fd_map[fd] = pipeinfo
    gatherer.register(fd)
    pass

  # Things to remember
  pipe_readers = {}

  # do something once in a while.
  report_time = datetime.datetime.now()
  driver_state = DriverState.Running
  exit_request_time = None

  while driver_state != DriverState.Done:
    if exit_request_time:
      if datetime.datetime.now() >= exit_request_time:
        driver_state = DriverState.Done
        break
      pass

    try:
      current_time = datetime.datetime.now()
      dt = in_seconds(current_time - report_time)
      if dt > 5:
        report_time = current_time
        for proc_name, process in processes:
          printer.line(proc_name, "driver", "PID=%d retcode %s" % (process.pid, str(process.returncode)))
          pass
        pass

      receiving = gatherer.poll(timeout)

      for fd, event in receiving:
        (proc_name, process, pipetag, pipe) = fd_map.get(fd)
        reader_key = proc_name + "." + pipetag
        if event & (select.POLLIN | select.POLLPRI):
          reader = pipe_readers.get(reader_key)
          if reader is None:
            reader = PipeReader(pipe, tag=reader_key)
            pipe_readers[reader_key] = reader
            pass

          line = reader.readline()

          if line == b'':
            tlog.debug("driver closing fd %d fo reading empty" % fd)
            gatherer.unregister(fd)
            del fd_map[fd]
            pipe_readers[reader_key] = None
            pass
          elif line is not None:
            line = line.strip()
            if line:
              # This is the real progress.
              printer.line(proc_name, pipetag, line)
              pass
            pass
          # Skip checking the closed fd until nothing to read
          continue

        #
        if event & (select.POLLHUP | select.POLLNVAL | select.POLLERR):
          pipe.close()
          gatherer.unregister(fd)
          del fd_map[fd]
          # I tried to del and seems to be not very happy.
          pipe_readers[reader_key] = None
          pass
        pass

      # deal with process
      proc_name: str
      process: subprocess.Popen
      for proc_name, process in processes:
        retcode = process.poll() # retcode should be 0 so test it against None
        if retcode is not None:
          printer.exit(proc_name, process.pid, retcode)
          processes.remove((proc_name, process))
          driver_state = DriverState.Stopping if len(processes) == 0 else driver_state

          # Something went wrong. Try to kill the rest.
          if retcode != 0:
            # retcode sucks. cannot tell much about the failier.
            drive_process_retcode = retcode
            _terminate_all(processes)
            pass
          pass
        else:
          try:
            os.kill(process.pid, 0)  # This does not actually kill; it checks if PID exists.
          except OSError:
            # Process is gone even though poll() returned None
            printer.error(proc_name, "PID=%d appears to have exited unexpectedly." % process.pid, pid=process.pid)
            processes.remove((proc_name, process))
            driver_state = DriverState.Stopping if len(processes) == 0 else driver_state
            drive_process_retcode = -1
            _terminate_all(processes)
            pass
          pass
        pass

      #
      if len(fd_map) == 0 or len(processes) == 0:
        driver_state = DriverState.Done
        pass

      pass

    except KeyboardInterrupt as exc:
      printer.line(name, "driver", "Stop requested.")
      drive_process_retcode = 0
      exit_request_time = datetime.datetime.now() + datetime.timedelta(0, 10, 0)
      driver_state = DriverState.Stopping
      _terminate_all(processes)
      pass

    except Exception as exc:
      printer.error(name, "Aborting due to exception. -- %s" % (traceback.format_exc()))
      drive_process_retcode = 1
      # Wait max of 10 seconds
      exit_request_time = datetime.datetime.now() + datetime.timedelta(0, 10, 0)
      driver_state = DriverState.Stopping
      _terminate_all(processes)
      pass
    pass
  return drive_process_retcode
