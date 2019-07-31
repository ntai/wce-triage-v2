#!/usr/bin/python3

import os, sys, subprocess, urllib, datetime, json, traceback, signal
from wce_triage.lib.util import *
from wce_triage.lib.timeutil import *
from wce_triage.ops.run_state import *

start_time = datetime.datetime.now()


def handler_stop_signals(signum, frame):
  global running
  running = False
  pass


def wipe_disk(dest_dev, n_sectors, output=sys.stderr):
  '''zero wipes disk.
dest_dev: Device file eg. /dev/sdc, will be destroyed with zero.
n_sectors: number of sectors.
'''
  global running
  running = True
  
  if not is_block_device(dest_dev):
    return 1

  pattern_size = 4 * 1024 * 1024
  pattern = bytearray(pattern_size)
  
  device = open(dest_dev, 'wb')
  remaining = n_sectors
  report_time = start_time
  loop_count = 0
  report_count = 0
  speeds = 100 * [0]
  
  signal.signal(signal.SIGINT, handler_stop_signals)
  signal.signal(signal.SIGTERM, handler_stop_signals)

  while running and remaining > 0:
    write_start = datetime.datetime.now()
    if remaining >= (pattern_size / 512):
      device.write(pattern)
      remaining -= (pattern_size / 512)
    else:
      device.write(pattern[:remaining*512])
      remaining = 0
      pass
    device.flush()
    os.fsync(device.fileno())
    write_end = datetime.datetime.now()
    speeds[loop_count % 100] = (pattern_size / 512) / in_seconds(write_end - write_start)

    current_time = write_end
    dt_last_report = current_time - report_time

    if in_seconds(dt_last_report) > 0.9:
      report_time = current_time
      dt_elapsed = in_seconds(current_time - start_time)
      percentage_done = float(n_sectors - remaining) / float(n_sectors)
      # sectors_per_second = float(n_sectors - remaining) / dt_elapsed
      if loop_count >= len(speeds):
        rates = sorted(speeds)[10:90]
      else:
        rates = speeds
        pass
      sectors_per_second = sum(rates) / len(rates)
      time_reamining = remaining / sectors_per_second
      progress = min(99, max(1, round(100*percentage_done)))

      report = { "event": "zerowipe",
                 "message": {"device": dest_dev,
                             "runMessage": "%d of %d sectors wiped." % (n_sectors - remaining, n_sectors),
                             "runStatus": RUN_STATE[RunState.Running.value],
                             "startTime": start_time.isoformat(),
                             "currentTime": current_time.isoformat(),
                             "progress": progress,
                             "timeReamining" : round(time_reamining),
                             "runTime" : round(in_seconds(dt_elapsed)),
                             "runEstimate" : round(time_reamining+in_seconds(dt_elapsed)),
                             "sectorsPerSecond": sectors_per_second,
                             "totalSectors": n_sectors,
                             "remainingSectors": remaining}}
      print(json.dumps(report), file=output, flush=True)
      report_count += 1
      pass
    loop_count += 1
    pass

  device.close()
  current_time = datetime.datetime.now()
  dt_elapsed = current_time - start_time

  if running:
    report = { "event": "zerowipe",
               "message" : {"device": dest_dev,
                            "runMessage": "%d of %d sectors wiped." % (n_sectors - remaining, n_sectors),
                            "runStatus": RUN_STATE[RunState.Success.value],
                            "startTime": start_time.isoformat(),
                            "currentTime": current_time.isoformat(),
                            "progress": 100,
                            "runTime" : round(in_seconds(dt_elapsed)),
                            "runEstimate" : round(in_seconds(dt_elapsed)),
                            "timeReamining" : 0,
                            "sectorsPerSecond": n_sectors / in_seconds(dt_elapsed),
                            "totalSectors": n_sectors,
                            "remainingSectors": 0}}
  else:
    report = { "event": "zerowipe",
               "message" : {"device": dest_dev,
                            "runMessage": "%d of %d sectors wiped." % (n_sectors - remaining, n_sectors),
                            "runStatus": RUN_STATE[RunState.Failed.value],
                            "startTime": start_time.isoformat(),
                            "currentTime": current_time.isoformat(),
                            "progress": 999,
                            "runTime" : round(in_seconds(dt_elapsed)),
                            "runEstimate" : round(in_seconds(dt_elapsed)),
                            "timeReamining" : 0,
                            "sectorsPerSecond": n_sectors / in_seconds(dt_elapsed),
                            "totalSectors": n_sectors,
                            "remainingSectors": 0}}

    pass
  print(json.dumps(report), file=output, flush=True)
  pass



def wipe(short_wipe, device):
  parted = subprocess.run(['parted', device, 'unit', 's', 'print'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  disk_line = 'Disk %s:' % device
  n_sectors = None
  for line in parted.stdout.decode('iso-8859-1').splitlines():
    line = line.strip()
    if disk_line in line:
      disksize = line.split(':')[1].strip()
      if disksize[-1] != 's':
        print("parted returned unexpedted output.")
        sys.exit(1)
        break
      else:
        disksize = disksize[:-1]
        n_sectors = int(disksize)
        pass
      pass
    pass

  if short_wipe:
    # wipe first 1Mb
    n_sectors = 2*1024
    pass

  try:
    result = wipe_disk(device, n_sectors)
  except Exception as exc:
    run_time = round(in_seconds( datetime.datetime.now() - start_time))
    error_message = traceback.format_exc()
    report = { "event": "zerowipe",
               "message": {"device": device,
                           "runMessage": "Wiping failed with " + error_message,
                           "runStatus": RUN_STATE[RunState.Failed.value],
                           "progress": 999,
                           "runTime" : run_time,
                           "runEstimate" : run_time}}
    print(json.dumps(report), file=sys.stderr, flush=True)

    print("wipe disk failed with exception: %s" % error_message)
    tlog.info(error_message)
    sys.exit(1)
    pass
  pass




if __name__ == "__main__":
  if len(sys.argv) < 2:
    sys.stderr.write('zerowipe.py [-s] <wiped>\n')
    sys.exit(1)
    pass
    
  short_wipe = False
  device = sys.argv[1]
  if device == '-s':
    short_wipe = True
    device = sys.argv[2]
    pass
  
  if not is_block_device(device):
    sys.stderr.write("%s is not a block device.\n" % device)
    sys.exit(1)
    pass

  try:
    wipe(short_wipe, device)
  except Exception as exc:
    sys.stdout.write(traceback.format_exc())
    sys.exit(1)
    pass
  pass
    
