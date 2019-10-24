#!/usr/bin/python3
"""Tool to clone USB sticks.

This reads the partition map using parted and figures out the size of copy.
If there is no partition, then this is no go.
"""

import os, sys, subprocess, urllib, datetime, json, traceback, signal, time
from ..lib.util import *
from ..lib.timeutil import *
from ..components.computer import Computer
from ..components.disk import Partition, DiskPortal, PartitionLister
import threading
import io
from collections import namedtuple
import queue
import mmap

def handler_stop_signals(signum, frame):
  global running
  running = False
  pass

class RawWriter(threading.Thread):

  def __init__(self, destpath, queue_size, verbose=False):
    super().__init__()
    self.destpath = destpath
    self.dest = None
    self.queue = queue.Queue(maxsize=queue_size)
    self.size_written = 0
    self.verbose = False
    pass

  def start(self):
    super().start()
    self.dest = io.FileIO(self.destpath, "w")
    pass
  
  def run(self):
    """
    """
    global running
    while running:
      try:
        payload = self.queue.get()
        if payload is None:
          break
        self.dest.write(payload)
        self.size_written += len(payload)
        if self.verbose:
          print("writer: written {}, payload {}".format(self.size_written, len(payload)))
          pass
        pass
      finally:
        self.queue.task_done()
        pass
      pass
    self.dest.close()
    pass
  pass

class ProgressReporter:
  def __init__(self, total_size, output=sys.stdout):
    self.start_time = datetime.datetime.now()
    self.report_time = self.start_time
    self.current_time = None
    self.total_size = total_size
    self.output = output
    pass
  
  def maybe_report(self, size_done):
    self.current_time = datetime.datetime.now()
    dt_last_report = self.current_time - self.report_time

    if in_seconds(dt_last_report) >= 1.0:
      self.report_time = self.current_time
      self.report(size_done)
      pass
    pass

  def report(self, size_done):
    self.report_time = self.current_time
    dt_elapsed = in_seconds(self.current_time - self.start_time)
    # Note that this is how much source is read, not written to destination.
    percentage_done = float(size_done) / float(self.total_size)
    progress = min(99, max(1, round(100*percentage_done)))
    report = { "event": "binarycopy",
               "message": {"runMessage": "%d of %d bytes copied." % (size_done, self.total_size),
                           "startTime": self.start_time.isoformat(),
                           "currentTime": self.current_time.isoformat(),
                           "progress": progress,
                           "runTime" : round(in_seconds(dt_elapsed)),
                           "total_bytes": self.total_size,
                           "remaining": self.total_size - size_done}}
    print(json.dumps(report), file=self.output, flush=True)
    pass
  pass


def get_min_written_size(size_written, writers):
  for writer in writers:
    size_written = min(size_written, writer.size_written)
    pass
  return size_written


def binary_copy(source, total_size, dests, output=sys.stderr):
  """Binary copy bits to disk
source: file handle
total_size: size to copy
dest_dev: Device file eg. /dev/sdc
"""
  global running
  running = True
  
  buffer_size = 2**20
  n_buffers = 100
  buffers = []

  buffers = [ mmap.mmap(-1, buffer_size) for i in range(n_buffers) ]
  writers = [ RawWriter(dst, n_buffers/2, verbose=dst == dests[0]) for dst in dests ]
  for writer in writers: writer.start()

  loop_count = 0
  size_done = 0
  
  #signal.signal(signal.SIGINT, handler_stop_signals)
  #signal.signal(signal.SIGTERM, handler_stop_signals)

  progress_reporter = ProgressReporter(total_size, output=output)

  while running and (size_done < total_size):
    buffer = buffers[loop_count % n_buffers]

    size_read = source.readinto(buffer)
    if size_read == None:
      break

    # So, what's hapenning here is that, the queue length is same as
    # the number of buffer, so when the queue is full, the producer has
    # to wait for queue.
    # In the end, all writes are done when the slowest one is done.
    
    if size_read == len(buffer):
      payload = buffer
    else:
      payload = buffer[:size_read]
      pass

    size_done += size_read

    for writer in writers:
      writer.queue.put( payload )
      pass

    if size_done >= total_size:
      for writer in writers:
        writer.queue.put( None )
        pass
      pass

    loop_count += 1

    # 
    size_written = get_min_written_size(size_done, writers)
    progress_reporter.maybe_report(size_written)
    pass

  for writer in writers:
    writer.queue.join()
    writer.join()
    size_written = get_min_written_size(size_done, writers)
    progress_reporter.maybe_report(size_written)
    pass

  size_written = get_min_written_size(size_done, writers)
  progress_reporter.report(size_written)
  pass


if __name__ == "__main__":
  if len(sys.argv) < 2:
    sys.stderr.write('binarycopy.py master [clones...]\n')
    sys.exit(1)
    pass
    
  disk_portal = DiskPortal()
  (added, changed, removed) = disk_portal.detect_disks()

  master = sys.argv[1]
  clones = sys.argv[2:]

  masterdisk = None
  for disk in disk_portal.disks:
    if disk.mounted:
      continue
    if disk.device_name == master:
      masterdisk = disk
      pass
    pass
  
  if masterdisk is not None:
    lister = PartitionLister(masterdisk)
    lister.execute()
    if len(masterdisk.partitions) == 0:
      print("master disk has no valid partition.")
      sys.exit(1)
      pass
    lastpart = masterdisk.partitions[-1]
    total_size = (lastpart.end_sector + 1)*512
    source = io.FileIO(master)
    pass
  else:
    if os.path.exists(master):
      fst = os.stat(master)
      total_size = fst.st_size
      source = io.FileIO(master)
      pass
    else:
      print("duh")
      sys.exit(1)
      pass
    pass
  
  print("total_size = {}".format(total_size))
  binary_copy(source, total_size, clones)
  pass
    
