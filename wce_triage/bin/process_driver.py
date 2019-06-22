#
# Probably, I need to deal with signals. That's gonna be future project.
#
import os, sys, subprocess, urllib, datetime, traceback


if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

from wce_triage.lib.util import *
from wce_triage.lib.timeutil import *
from collections import deque
import urllib.parse
import os

from collections import namedtuple
PipeInfo = namedtuple('PipeInfo', 'app, process, pipetag, pipe')

from enum import Enum

class DriverState(Enum):
  Running = 1
  Stopping = 2
  Done = 3
  pass

def _kill_all(processes):
  for proc_name, process in processes:
    process.kill()
    pass
  pass

def print_progress(msg):
  print(msg)
  sys.stdout.flush()
  pass


def drive_process(name, processes, pipes, encoding='iso-8859-1', timeout=0.25):
  #
  for proc_name, process in processes:
    print_progress("%s: %s PID=%d" % (name, proc_name, process.pid))
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
  pipe_fragments = {}

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
          print_progress("%s: %s PID=%d retcode %s" % (name, proc_name, process.pid, str(process.returncode)))
          pass
        pass

      # deal with process
      for proc_name, process in processes:
        retcode = process.poll() # retcode should be 0 so test it against None
        if retcode is not None:
          print_progress("%s: %s exited with %d" % (name, proc_name, retcode))
          processes.remove((proc_name, process))
          driver_state = DriverState.Done if len(processes) == 0 else driver_state
          
          # Something went wrong. Try to kill the rest.
          if retcode != 0:
            # retcode sucks. cannot tell much about the failier.
            drive_process_retcode = retcode
            _kill_all(processes)
            pass
          pass
        pass

      receiving = gatherer.poll(timeout)
    
      for fd, event in receiving:
        (proc_name, process, pipe_name, pipe) = fd_map.get(fd)
        if event & (select.POLLIN | select.POLLPRI):
          data = pipe.read(1)
          if data == b'':
            print_progress("%s: %s.%s closed." % (name, proc_name, pipe_name))
            # this fd closed.
            gatherer.unregister(fd)
            del fd_map[fd]
            pass
          elif len(data) > 0:
            pipe_name = proc_name + "." + pipe_name
            if not pipe_name in pipe_fragments:
              pipe_fragments[pipe_name] = deque()
              pass
            queue = pipe_fragments[pipe_name]
            while True:
              newline = data.find(b'\n')
              if newline < 0:
                newline = data.find(b'\r')
                pass
              if newline < 0:
                if data:
                  queue.append(data)
                  pass
                break
              leftover = b""
              while len(queue) > 0:
                leftover = leftover + queue.popleft()
                pass
              leftover = leftover + data[:newline]
              text = leftover.decode(encoding).strip()
              if text:
                print_progress(pipe_name + ":" + text)
                pass
              data = data[newline+1:]
              pass
            pass
          # Skip checking the closed fd until nothing to read
          continue
      
        # 
        if event & (select.POLLHUP | select.POLLNVAL | select.POLLERR):
          print_progress("%s: %s.%s closed." % (name, proc_name, pipe_name))
          # this fd closed.
          pipe.close()
          gatherer.unregister(fd)
          del fd_map[fd]
          pass
        pass
      pass

    except KeyboardInterrupt as exc:
      print_progress("%s: Stop requested." % (name))
      drive_process_retcode = 0
      exit_request_time = datetime.datetime.now() + datetime.timedelta(0, 10, 0)
      driver_state = DriverState.Stopping
      _kill_all(processes)
      pass

    except Exception as exc:
      printt("%s: Aborting due to exception.\n%s" % (name, traceback.format_exc()))
        
      drive_process_retcode = 1
      # Wait max of 10 seconds
      exit_request_time = datetime.datetime.now() + datetime.timedelta(0, 10, 0)
      driver_state = DriverState.Stopping
      _kill_all(processes)
      pass
    pass
  return drive_process_retcode
