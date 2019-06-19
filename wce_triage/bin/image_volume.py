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
import urllib.parse
import os
from bin.process_driver import *

def save_disk(source, dest, encoding='iso-8859-1'):

  # compressor to use (gzip!)
  comp = get_file_compression_app(dest)

  parsed = urllib.parse.urlsplit(dest)

  if parsed.scheme:
    # First, take a look at where the destination is.
    # When it's over network, create a named pipe, and write partclone/compressor
    # to write to it.
    subprocess.run("mkdir -p /tmp/www/wce-disk-images", shell=True)

    filename = os.path.split(parsed.path)[1]
    fifopath = os.path.join("/tmp/www/wce-disk-images", filename)
    
    subprocess.run(["mkfifo", fifopath])

    remotedest = urllib.parse.urljoin(dest, ".")

    argv_curl = [ "curl", "-s", "--data-binary", "-T", "-O", fifopath,  remotedest]
    dest = fifopath
    pass
  else:
    argv_curl = None
    pass

  # existance of named pipe as intermediate output makes things
  # mighty confusing.

  # When the compessor is used, it always reads from partclone's stdout
  # The compressor output is always the "dest" which is "local" file.
  # It's the actual file, or fifo.
  # However, don't open the fifo until curl listens.
  if comp:
    argv_comp = comp[0] + comp[1]
    partclone_output = "-"
    partclone_stdout = subprocess.PIPE
    pass
  else:
    argv_comp = None
    # Let partclone write to the local file.
    partclone_output = dest
    partclone_stdout = None
    pass

  # partclone
  argv_partclone = [ "partclone.ext4", "-c", "-s", source, "-o", partclone_output ]

  # wire up the apps.
  pipes = []

  # First the curl to make sure fifo is listening
  # (would this race?)
  # It's weird to start from downstream but named pipe is weird.
  if argv_curl:
    curl = subprocess.Popen(argv_curl, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processes.append(("curl", curl))
    # Curl's stdin/out not used at all. Listen to both.
    pipes.append(PipeInfo("curl", curl, "stdout", curl.stdout))
    pipes.append(PipeInfo("curl", curl, "stderr", curl.stderr))
    pass
  else:
    curl = None
    pass

  # Now, the partclone's turn. The standard out is either a pipe to compressor, or nothing.
  # If the output is file or fifo, this should open the output.
  partclone = subprocess.Popen(argv_partclone, stdout=partclone_stdout, stderr=subprocess.PIPE)
  processes.append((argv_partclone[0], partclone))

  pipes.append(PipeInfo("partclone", partclone, "stderr", partclone.stderr))

  # Now the compressor. The output goes to local file. Time to open the desination file/fifo.
  # Input is always the partclone's stdout when the compressor exists.
  if argv_comp:
    comp = subprocess.Popen(argv_comp, stdin=partclone.stdout, stdout=open(dest, "wb"), stderr=subprocess.PIPE)
    processes.append((argv_comp[0], comp))
    pipes.append(PipeInfo(argv_comp[0], comp, "stderr", comp.stderr))
    pass
  else:
    comp = None
    pass

  # all the processes are up. Drive them.
  drive_process("IMAGER", processes, pipes)
  pass


if __name__ == "__main__":
  if len(sys.argv) != 3:
    sys.stderr.write('image_volume.py <source> <dest>\n  source: device file\n  dest: URL\n')
    sys.exit(1)
    pass
    
  save_disk(sys.argv[1], sys.argv[2])
  pass
