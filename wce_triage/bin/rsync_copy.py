#!/usr/bin/python3
import sys
import subprocess
from typing import List
from wce_triage.bin.process_driver import PipeInfo, drive_process

def rsync_copy(source: str, dests: List[str]) -> int:
  # signal.signal(signal.SIGINT, handler_stop_signals)
  # signal.signal(signal.SIGTERM, handler_stop_signals)
  bin_name = "RSYNC-COPY"
  pipes = []
  processes = []
  for destination in dests:
    dest = destination.split(':')
    key, filename = ("-", dest[0]) if len(dest) == 1 else (dest[0], dest[1])
    argv_rsync = ["rsync", "--info=progress2", "-W", "-t", "--inplace", "--force", source, filename]
    rsync = subprocess.Popen(argv_rsync, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processes.append((f"{key}:{filename}", rsync))
    pipes.append(PipeInfo(key + ":" + filename + ":", rsync, "stdout:%d" % rsync.pid, rsync.stdout))
    pipes.append(PipeInfo(key + ":" + filename + ":", rsync, "stderr:%d" % rsync.pid, rsync.stderr))
  return drive_process(bin_name, processes, pipes)


if __name__ == "__main__":
  if len(sys.argv) < 2:
    usage = '''rsync_copy.py source_file destination[,destination...]
  desination:
    key:destination file path
    key is used to ID the copying file.'''
    sys.stderr.write(usage)
    sys.exit(1)
    pass

  source = sys.argv[1]
  dests = sys.argv[2:]
  exit(rsync_copy(source, dests))
