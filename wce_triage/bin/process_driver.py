#
# Probably, I need to deal with signals. That's gonna be future project.
#
import os, sys, subprocess, urllib, datetime, traceback


if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

from ..lib.util import *
from ..lib.timeutil import *
from ..lib.pipereader import *
from collections import deque
import urllib.parse
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

class Printer:
  def __init__(self, name):
    self.name = name
    self.prefix = name + ": "
    self.error_prefix = name + ".ERROR: "
    pass
  
  def print_progress(self, msg):
    msg = msg.strip()
    if len(msg) == 0:
      return
    tlog.debug(self.prefix + msg)
    print(self.prefix + msg, file=sys.stderr, flush=True)
    pass

  def print_error(self, msg):
    msg = msg.strip()
    if len(msg) == 0:
      return
    tlog.debug(self.error_prefix + msg)
    print('\n'.join([ self.error_prefix + line for line in msg.split('\n') ]), file=sys.stderr, flush=True)
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
  printer = Printer(name)
  
  for proc_name, process in processes:
    printer.print_progress("%s PID=%d" % (proc_name, process.pid))
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
          printer.print_progress("%s PID=%d retcode %s" % (proc_name, process.pid, str(process.returncode)))
          pass
        pass

      # deal with process
      for proc_name, process in processes:
        retcode = process.poll() # retcode should be 0 so test it against None
        if retcode is not None:
          if retcode == 0:
            printer.print_progress("%s exited with %d" % (proc_name, retcode))
          else:
            printer.print_error("%s exited with %d" % (proc_name, retcode))
            pass
          processes.remove((proc_name, process))
          driver_state = DriverState.Stopping if len(processes) == 0 else driver_state

          # Something went wrong. Try to kill the rest.
          if retcode != 0:
            # retcode sucks. cannot tell much about the failier.
            drive_process_retcode = retcode
            _terminate_all(processes)
            pass
          pass
        pass

      receiving = gatherer.poll(timeout)
    
      for fd, event in receiving:
        (proc_name, process, pipe_name, pipe) = fd_map.get(fd)
        pipe_name = proc_name + "." + pipe_name
        if event & (select.POLLIN | select.POLLPRI):
          reader = pipe_readers.get(pipe_name)
          if reader is None:
            reader = PipeReader(pipe, tag=pipe_name)
            pipe_readers[pipe_name] = reader
            pass

          line = reader.readline()

          if line == b'':
            tlog.debug("driver closing fd %d fo reading empty" % fd)
            gatherer.unregister(fd)
            del fd_map[fd]
            pipe_readers[pipe_name] = None
            pass
          elif line is not None:
            line = line.strip()
            if line:
              # This is the real progress.
              printer.print_progress(pipe_name + ":" + line)
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
          pipe_readers[pipe_name] = None
          pass
        pass

      #
      if len(fd_map) == 0:
        driver_state = DriverState.Done
        pass

      pass

    except KeyboardInterrupt as exc:
      printer.print_progress("Stop requested.")
      drive_process_retcode = 0
      exit_request_time = datetime.datetime.now() + datetime.timedelta(0, 10, 0)
      driver_state = DriverState.Stopping
      _terminate_all(processes)
      pass

    except Exception as exc:
      printer.print_error("Aborting due to exception. -- %s" % (traceback.format_exc()))
      drive_process_retcode = 1
      # Wait max of 10 seconds
      exit_request_time = datetime.datetime.now() + datetime.timedelta(0, 10, 0)
      driver_state = DriverState.Stopping
      _terminate_all(processes)
      pass
    pass
  return drive_process_retcode
