#
# 
#
import os, sys, subprocess, urllib, datetime

if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

from lib.util import *
from lib.timeutil import *
from collections import deque
from bin.process_driver import *

def load_disk(source, dest_dev):

  transport_scheme = get_transport_scheme(source)
  decomp = get_file_decompression_app(source)

  # First, take a look at where is the source.
  # If it's over a network, use wget to get it.
  # The source is used up so mark it as "-"

  argv_wget = None
  if transport_scheme:
    argv_wget = [ "wget", "-q", "-O", "-", source ]
    source = "-"
  else:
    pass
    
  # When the source is still available, the decompressor
  # uses it as the source when decomp is needed
  if decomp:
    argv_decomp = decomp[0] + decomp[1]
    if source != "-":
      argv_decomp.append(source)
      source = "-"
      pass
    pass
  else:
    argv_decomp = None
    pass

  processes = []
  pipes = []

  # So, for partclone, the source is whatever upstream hands down.
  argv_partclone = [ "partclone.ext4", "-r", "-s", source, "-o", dest_dev ]

  # wire up the apps
  if argv_wget:
    wget = subprocess.Popen(argv_wget, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processes.append(("wget", wget))
    pipes.append(PipeInfo("wget", wget, "stderr", wget.stderr))
    pass
  else:
    wget = None
    pass

  if argv_decomp:
    decomp_stdin = wget.stdout if wget else None
    decomp = subprocess.Popen(argv_decomp, stdin=decomp_stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processes.append((argv_decomp[0], decomp))
    pipes.append(PipeInfo(argv_decomp[0], decomp, "stderr", decomp.stderr))
    pass
  else:
    decomp = None
    pass

  # stdin of partclone is one of upstream, or the file in argv
  if decomp:
    partclone_stdin = decomp.stdout
  elif wget:
    partclone_stdin = wget.stdout
  else:
    if source == "-":
      raise Exception("the source should be a pipe to stdin.")
    partclone_stdin = None
    pass

  partclone = subprocess.Popen(argv_partclone, stdin=partclone_stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  processes.append((argv_partclone[0], partclone))
  pipes.append(PipeInfo("partclone", partclone, "stdout", partclone.stdout))
  pipes.append(PipeInfo("partclone", partclone, "stderr", partclone.stderr))

  # all the processes are up. Drive them.
  drive_process("LOADER", processes, pipes)
  pass

if __name__ == "__main__":
  if len(sys.argv) != 3:
    sys.stderr.write('restore_volume.py <source> <destdev>\n  source: URL\n  destdev: device file\n')
    sys.exit(1)
    pass
    
  load_disk(sys.argv[1], sys.argv[2])
  pass
