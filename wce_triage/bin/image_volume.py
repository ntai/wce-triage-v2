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

def save_disk(source, dest, encoding='iso-8859-1'):

  # compressor to use (gzip!)
  comp = get_file_compression_app(dest)

  parsed = urllib.parse.urlsplit(dest)

  if parsed.scheme:
    # First, take a look at where is the destination is.
    # When it's over network, create a named pipe, and write partclone/decompressor
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
    argv_comp = decomp[0] + decomp[1] + ["-"]
    partclone_output = "-"
    partclone_stdout = subprocess.PIPE
    pass
  else:
    # Let partclone write to the local file.
    partclone_output = dest
    partclone_stdout = None
    pass

  # partclone
  argv_partclone = [ "partclone.ext4", "-c", "-s", source, "-o", partclone_output ]

  # wire up the apps.

  # gatherer gathers pipe outs
  gatherer = select.poll()

  # fdmap 
  fd_map = {}

  # First the curl to make sure fifo is listening
  # (would this race?)
  # It's weird to start from downstream but named pipe is weird.
  if argv_curl:
    curl = subprocess.Popen(argv_curl, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processes.append(("curl", curl))
    # Curl's stdin/out not used at all. Listen to both.
    fd_map[curl.stdout.fileno()] = ("curl", curl, "stdout", curl.stdout)
    fd_map[curl.stderr.fileno()] = ("curl", curl, "stderr", curl.stderr)
    pass
  else:
    curl = None
    pass

  # Now, the partclone's turn. The standard out is either a pipe to compressor, or nothing.
  # If the output is file or fifo, this should open the output.
  partclone = subprocess.Popen(argv_partclone, stdout=partclone_stdout, stderr=subprocess.PIPE)
  processes.append((argv_partclone[0], partclone))

  fd_map[partclone.stderr.fileno()] = ("partclone", partclone, "stderr", partclone.stderr)

  # Now the compressor. The output goes to local file. Time to open the desination file/fifo.
  # Input is always the partclone's stdout when the compressor exists.
  if argv_comp:
    comp = subprocess.Popen(argv_comp, stdin=partclone.stdout, stdout=open(dest, "wb"), stderr=subprocess.PIPE)
    processes.append((argv_comp[0], comp))
    fd_map[comp.stderr.fileno()] = (argv_comp[0], comp, "stderr", comp.stderr)
    pass
  else:
    comp = None
    pass

  # all the processes are up. Drive them.

  timeout = 0.25

  pipes = {}
  report_time = datetime.datetime.now()

  while len(processes) > 0:
    current_time = datetime.datetime.now()
    dt = in_seconds(current_time - report_time)
    if dt > 5:
      report_time = current_time
      for proc_name, process in processes:
        print("IMAGER: %s PID=%d retcode %s" % (proc_name, process.pid, str(process.returncode)))
        pass
      pass

    # deal with process
    for proc_name, process in processes:
      retcode = process.poll() # retcode should be 0 so test it against None
      if retcode is not None:
        print("IMAGER: %s exited with %d" % (proc_name, retcode))
        processes.remove((proc_name, process))

        # Something went wrong. Try to kill the rest.
        if retcode != 0:
          for proc_name, remain in processes:
            remain.kill()
            pass
          pass
        pass
      pass

    receiving = gatherer.poll(timeout)
    
    for fd, event in receiving:
      (proc_name, process, pipe_name, pipe) = fd_map.get(fd)
      if event & (select.POLLIN | select.POLLPRI):
        data = pipe.read(1)
        if data == b'':
          print("IMAGER: %s.%s closed." % (proc_name, pipe_name))
          # this fd closed.
          gatherer.unregister(fd)
          del fd_map[fd]
          pass
        elif len(data) > 0:
          pipe_name = proc_name + "." + pipe_name
          if not pipe_name in pipes:
            pipes[pipe_name] = deque()
            pass
          queue = pipes[pipe_name]
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
              print(pipe_name + ":" + text)
              pass
            data = data[newline+1:]
            pass
          pass
        # Skip checking the closed fd until nothing to read
        continue
      
      # 
      if event & (select.POLLHUP | select.POLLNVAL | select.POLLERR):
        print("IMAGER: %s.%s closed." % (proc_name, pipe_name))
        # this fd closed.
        pipe.close()
        gatherer.unregister(fd)
        del fd_map[fd]
        pass
      pass
    pass
  pass

if __name__ == "__main__":
  if len(sys.argv) != 3:
    sys.stderr.write('image_volume.py <source> <dest>\n  source: device file\n  dest: URL\n')
    sys.exit(1)
    pass
    
  save_disk(sys.argv[1], sys.argv[2])
  pass
