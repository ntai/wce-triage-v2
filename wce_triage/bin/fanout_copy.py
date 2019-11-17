#!/usr/bin/python3

import os, sys, subprocess, urllib, datetime, json, traceback, signal, stat
from ..lib.util import *
from ..lib.timeutil import *
from ..ops.run_state import *

start_time = datetime.datetime.now()


def handler_stop_signals(signum, frame):
  global running
  running = False
  pass


def fanout_copy(source_file, destinations, output=sys.stderr):
  '''Copy a file to multiple locations. (aka duplication)
'''
  global running
  running = True
  
  source_file_size = None

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

  try:
    source_fd = open(source_file, "rb", buffering=0)
  except Exception as exc:
    print(traceback.format_exc())
    sys.exit(1)
    pass

  copybuf_size = 4 * 1024 * 1024
  copybuf = bytearray(copybuf_size)
  
  _destinations = []
  dest_files = []

  destinations = [ (d[0], d[1]) if len(d) == 2 else (None, d[0]) for d in [dest.split(':') for dest in destinations] ]

  for key, dest_path in destinations:
    try:
      _destinations.append((open(dest_path, 'wb'), dest_path, key))
      dest_files.append(dest_path)
    except Exception as exc:
      # Clean up the mess if I can.
      for dest_fd in dest_fds:
        try:
          dest_fd.close()
        except:
          pass
        pass
      
      for dest_file in dest_files:
        try:
          os.unlink(dest_file)
        except:
          pass
        pass

      print(traceback.format_exc())
      sys.exit(1)
      pass
    pass

  progress = 1
  remaining = source_file_size
  report_time = start_time
  loop_count = 0
  report_count = 0
  speeds = 100 * [0]
  sofar = 0
  time_reamining = 0
  bytes_per_second = 1
  invalid_fds = {}
  
  signal.signal(signal.SIGINT, handler_stop_signals)
  signal.signal(signal.SIGTERM, handler_stop_signals)

  while running and remaining > 0:
    write_start = datetime.datetime.now()

    copy_size = copybuf_size if remaining >= copybuf_size else remaining

    try:
      bytesread = source_fd.readinto(copybuf)
      remaining -= bytesread
    except Exception as exc:
      running = False
      current_time = datetime.datetime.now()
      dt_elapsed = in_seconds(current_time - start_time)
      report = {"key": key,
                "verdict": "Read failed. %s" % exc.format_exc(),
                "runMessage": "%d of %d bytes copied." % (sofar, source_file_size),
                "runStatus": RUN_STATE[RunState.Failed.value],
                "startTime": start_time.isoformat(),
                "currentTime": current_time.isoformat(),
                "progress": progress,
                "timeReamining" : 0,
                "runTime" : round(in_seconds(dt_elapsed)),
                "runEstimate" : 0,
                "bytesPerSecond": bytes_per_second,
                "totalBytes": source_file_size,
                "remainingBytes": remaining}
      print(json.dumps(report), file=output, flush=True)
      continue
      
    sofar += bytesread

    valid_data = copybuf if copy_size == copybuf_size else copybuf[:bytesread]
    
    for dest_fd, dest_path, key in _destinations:
      if dest_fd in invalid_fds:
        continue

      try:
        dest_fd.write(valid_data)
        dest_fd.flush()
        os.fsync(dest_fd.fileno())
      except Exception as exc:
        invalid_fds[dest_fd] = True
        current_time = datetime.datetime.now()
        dt_elapsed = in_seconds(current_time - start_time)
        report = {"key": key,
                  "verdict": exc.format_exc(),
                  "runMessage": "Write failed. %d of %d bytes copied." % (sofar, source_file_size),
                  "runStatus": RUN_STATE[RunState.Failed.value],
                  "startTime": start_time.isoformat(),
                  "currentTime": current_time.isoformat(),
                  "progress": progress,
                  "timeReamining" : 0,
                  "runTime" : round(in_seconds(dt_elapsed)),
                  "runEstimate" : 0,
                  "bytesPerSecond": bytes_per_second,
                  "totalBytes": source_file_size,
                  "remainingBytes": remaining}
        print(json.dumps(report), file=output, flush=True)
        pass
      pass

    write_end = datetime.datetime.now()
    speeds[loop_count % 100] = copybuf_size / in_seconds(write_end - write_start)

    current_time = write_end
    dt_last_report = current_time - report_time

    if in_seconds(dt_last_report) > 0.95:
      report_time = current_time
      dt_elapsed = in_seconds(current_time - start_time)
      percentage_done = float(source_file_size - remaining) / float(source_file_size)
      # bytes_per_second = float(source_file_size - remaining) / dt_elapsed
      if loop_count >= len(speeds):
        rates = sorted(speeds)[10:90]
      else:
        rates = speeds
        pass
      bytes_per_second = sum(rates) / len(rates)
      time_reamining = remaining / bytes_per_second
      # To show something when nothing is copy, use 1
      # To not get to 100 when rounded number is 100, stick in 99.
      progress = min(99, max(1, round(100*percentage_done)))

      for dest_fd, dest_path, key in _destinations:
        report = {"key": key,
                  "desination": dest_path,
                  "runMessage": "%d of %d bytes copied." % (sofar, source_file_size),
                  "runStatus": RUN_STATE[RunState.Running.value],
                  "startTime": start_time.isoformat(),
                  "currentTime": current_time.isoformat(),
                  "progress": progress,
                  "timeReamining" : round(time_reamining),
                  "runTime" : round(in_seconds(dt_elapsed)),
                  "runEstimate" : round(time_reamining+in_seconds(dt_elapsed)),
                  "bytesPerSecond": bytes_per_second,
                  "totalBytes": source_file_size,
                  "remainingBytes": remaining}
        print(json.dumps(report), file=output, flush=True)
        pass
      report_count += 1
      pass
    loop_count += 1
    pass

  for dest_fd, dest_path, key in _destinations:
    try:
      dest_fd.close()
      pass
    except Exception as exc:
      pass
    pass
  
  current_time = datetime.datetime.now()
  dt_elapsed = current_time - start_time

  if remaining > 0:
    for dest_fd, dest_path, key in _destinations:
      report = { "key": key,
                 "destination": dest_path,
                 "runMessage": "%d of %d bytes copied." % (sofar, source_file_size),
                 "runStatus": RUN_STATE[RunState.Failed.value],
                 "startTime": start_time.isoformat(),
                 "currentTime": current_time.isoformat(),
                 "progress": 999,
                 "timeReamining" : round(time_reamining),
                 "runTime" : round(in_seconds(dt_elapsed)),
                 "runEstimate" : round(time_reamining+in_seconds(dt_elapsed)),
                 "bytesPerSecond": bytes_per_second,
                 "totalBytes": source_file_size,
                 "remainingBytes": remaining}
      print(json.dumps(report), file=output, flush=True)
      pass
    pass
  else:
    for dest_fd, dest_path, key in _destinations:
      report = {"key": key,
                "verdict": "Speed: %d bytes/second" % round(source_file_size / in_seconds(dt_elapsed))
                "destination": dest_path,
                "runMessage": "Copying completed (%d bytes copied.)" % (source_file_size),
                "runStatus": RUN_STATE[RunState.Success.value],
                "startTime": start_time.isoformat(),
                "currentTime": current_time.isoformat(),
                "progress": 100,
                "runTime" : round(in_seconds(dt_elapsed)),
                "runEstimate" : round(in_seconds(dt_elapsed)),
                "timeReamining" : 0,
                "bytesPerSecond": source_file_size / in_seconds(dt_elapsed),
                "totalBytes": source_file_size,
                "remainingBytes": 0}
      print(json.dumps(report), file=output, flush=True)
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
  try:
    fanout_copy(source, dests)
  except Exception as exc:
    sys.stdout.write(traceback.format_exc())
    sys.exit(1)
    pass
  pass
    
