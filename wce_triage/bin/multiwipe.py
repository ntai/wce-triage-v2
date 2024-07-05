#!/usr/bin/python3

import os, sys, datetime, json, traceback, signal, subprocess
import threading
from ..lib.util import get_triage_logger
from ..lib.timeutil import in_seconds
from ..ops.run_state import RunState, RUN_STATE
import time

start_time = datetime.datetime.now()
tlog = get_triage_logger()
debugging = False

zeros_size = 2 ** 22
zeros = bytearray(zeros_size)

wipers = []
global wiping
wiping = True

def handler_stop_signals(signum, frame):
  global wiping
  wiping = False
  for wiper in wipers:
    wiper.stop_request()
    pass
  pass

def debuglog(msg):
  if debugging:
    print(msg, flush=True)
    tlog.debug(msg)
    pass
  pass


class Wiper(threading.Thread):
  def __init__(self, n_sectors, fd, dest, output=sys.stderr):
    '''zero wipes disk.
dest_dev: Device file eg. /dev/sdc, will be destroyed with zero.
n_sectors: number of sectors.
'''
    self.running = True
    self.zombie = True # I could use barrier
  
    self.device = fd
    self.dest = dest
    self.n_sectors = int(n_sectors)
    if int(n_sectors) != self.n_sectors:
      raise Exception("n_sectors is not int.")
    self.n_written = 0

    self.report_time = start_time
    self.loop_count = 0
    self.end_time = None
    super().__init__()
    pass
  
  def run(self):
    debuglog("%s is starting. %d/%d" % (self.dest, self.n_written, self.n_sectors))

    while self.running:
      remaining = self.n_sectors - self.n_written
      write_size = min(remaining * 512, len(zeros))
      try:
        if write_size < len(zeros):
          self.device.write(zeros[:write_size])
          self.running = False
          pass
        else:
          self.device.write(zeros)
          pass
        self.n_written += int(write_size / 512)
      except Exception as exc:
        debuglog("Error writing to %s\n%s" % (self.dest, traceback.format_exc()))
        self.running = False
        pass
      pass
    self.device.close()
    self.end_time = datetime.datetime.now()

    #while self.zombie:
    #  debuglog("%s is zombine. %d/%d" % (self.dest, self.n_written, self.n_sectors))
    #  time.sleep(0.5)
    #  pass
    pass

  def stop_request(self):
    self.running = False
    pass

  def _report(self):
    report = { "device": self.dest,
               "totalSectors": self.n_sectors,
               "n_written": self.n_written,
               "running": self.running}
    return report
    pass
  
  pass


class Reporter(threading.Thread):

  def __init__(self, wipers, output=sys.stderr):
    self.running = True
    self.output = output
    self.wipers = wipers[:]
    super().__init__()
    pass

  def run(self):

    while self.running:
      current_time = datetime.datetime.now()
      dt_duration = in_seconds(current_time - start_time)

      n_running = 0

      for wiper in self.wipers:
        report = wiper._report()
      
        report["startTime"] = start_time.isoformat()
        report["currentTime"] = current_time.isoformat()
        report["runTime"] = round(dt_duration, 1)

        running = report['running']
        n_sectors = report['totalSectors']
        n_written = report['n_written']

        if running:
          n_running += 1
          percentage_done = float(n_written) / float(n_sectors)
          progress = min(99, max(1, round(100*percentage_done)))
          report["progress"] = progress
          report["runMessage"] = "%d of %d sectors wiped." % (n_written, n_sectors)
          report["runStatus"] = RUN_STATE[RunState.Running.value]
          speed = float(n_written) / dt_duration
          time_reamining = float(n_sectors - n_written) / max(4096, speed)
          report["timeReamining"] = round(time_reamining)
          report["remainingSectors"] = n_sectors - n_written
          report["runEstimate"] = round(dt_duration + time_reamining, 1)
        else:
          if n_written == n_sectors:
            run_state = RunState.Success
            progress = 100
            report["runMessage"] = "Wipe completed. (%d of %d sectors)" % (n_written, n_sectors)
          else:
            run_state = RunState.Failed
            progress = 999
            report["runMessage"] = "Wipe failed. (%d of %d sectors)" % (n_written, n_sectors)
            pass

          report["runStatus"] = RUN_STATE[run_state.value]
          report["progress"] = progress
          report["timeReamining"] = 0
          report["remainingSectors"] = 0
          report["runEstimate"] = round(dt_duration, 1)
          pass

        msg = { "event": "zerowipe", "message": report }
        print(json.dumps(msg), file=self.output, flush=True)
        pass

      if n_running == 0:
        self.running = False
        break
      else:
        time.sleep(1)
        pass
      pass
    pass
  pass


def get_disk_total_sectors(device):
  parted = subprocess.run(['parted', device, 'unit', 's', 'print'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  disk_line = 'Disk %s:' % device
  n_sectors = None
  for line in parted.stdout.decode('iso-8859-1').splitlines():
    line = line.strip()
    if disk_line in line:
      disksize = line.split(':')[1].strip()
      if disksize[-1] != 's':
        debuglog("parted returned unexpedted output.")
        sys.exit(1)
        break
      else:
        disksize = disksize[:-1]
        n_sectors = int(disksize)
        pass
      pass
    pass
  return n_sectors


def zero_wipe(short_wipe, destination_specs):
  '''Wipe disks
'''
  if short_wipe:
    debuglog("Short wipe started.")
  else:
    debuglog("Wipe started.")
    pass

  destinations = []

  for key, dest in [ (d[0], d[1]) if len(d) == 2 else (d[0], d[0]) for d in [dest.split(':') for dest in destination_specs] ]:
    # This is for cleaning up when something goes wrong.
    try:
      destinations.append((open(dest, 'wb', buffering=0), dest, key))
      debuglog("Dest %s " % (key))
    except Exception as exc:
      # Clean up the mess if I can.
      tlog.info("Opening desination file %s failed with following error.\%s" (dest, traceback.format_exc()))
      sys.exit(1)
      pass
    pass

  signal.signal(signal.SIGINT, handler_stop_signals)
  
  for fd, dest, key in destinations:
    if short_wipe:
      # wipe first 1Mb
      n_sectors = 2048
    else:
      n_sectors = get_disk_total_sectors(dest)
      pass

    wiper = Wiper(n_sectors, fd, dest)
    wiper.start()
    wipers.append(wiper)
    debuglog("Wiper thread for %s start() called." % dest)
    pass
  debuglog("All wipers started.")

  reporter = Reporter(wipers)
  reporter.start()
  debuglog("Reporter started.")
    
  global wiping
  while wiping:
    is_alive = False

    for wiper in wipers:
      if wiper.running:
        is_alive = True
        pass
      pass
    if not is_alive:
      debuglog("No wiper is alive.")
      wiping = False
      break
    time.sleep(0.1)
    pass

  reporter.join(timeout=3)

  while True:
    n_alive = 0
    for wiper in wipers:
      wiper.zombie = False
      wiper.join(timeout=1)
      if wiper.is_alive():
        n_alive += 1
        pass
      pass
    if n_alive == 0:
      break
    pass

  debuglog("Reporter finished.")
  pass
  
  
if __name__ == "__main__":
  if len(sys.argv) < 2:
    sys.stderr.write('zerowipe.py [-s] <wiped...>\n')
    sys.exit(1)
    pass
    
  args = sys.argv[1:]
  short_wipe = False
  if args[0] == '-s':
    short_wipe = True
    args = args[1:]
    pass

  try:
    zero_wipe(short_wipe, args)
  except Exception as exc:
    sys.stdout.write(traceback.format_exc())
    sys.exit(1)
    pass
  pass
