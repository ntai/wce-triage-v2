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


def load_disk(source, dest_dev, encoding='iso-8859-1'):

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

  # So, for partclone, the source is whatever upstream hands down.
  argv_partclone = [ "partclone.ext4", "-r", "-s", source, "-o", dest_dev ]

  # wire up the apps
  if argv_wget:
    wget = subprocess.Popen(argv_wget, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processes.append(("wget", wget))
    pass
  else:
    wget = None
    pass

  if argv_decomp:
    decomp_stdin = wget.stdout if wget else None
    decomp = subprocess.Popen(argv_decomp, stdin=decomp_stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processes.append((argv_decomp[0], decomp))
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

  # all the processes are up. Drive them.

  # gatherer gathers error messages
  gatherer = select.poll()
  # Read from partclone putput
  gatherer.register(partclone.stdout)
  #
  for proc_name, process in processes:
    if process.stderr:
      gatherer.register(process.stderr)
      pass
    pass
    
  timeout = 0.25

  # fdmap initialized with partclone's stdout 
  fd_map = { partclone.stdout.fileno(): ("partclone", partclone, "stdout", process.stdout) }

  # Reading from stderr to collect error messages.
  for proc_name, process in processes:
    if process.stderr:
      fd_map[process.stderr.fileno()] = (proc_name, process, "stderr", process.stderr)
      pass
    pass

  pipes = {}

  report_time = datetime.datetime.now()

  while len(processes) > 0:
    current_time = datetime.datetime.now()
    dt = in_seconds(current_time - report_time)
    if dt > 5:
      report_time = current_time
      for proc_name, process in processes:
        print("LOADER: %s PID=%d retcode %s" % (proc_name, process.pid, str(process.returncode)))
        pass
      pass

    # deal with process
    for proc_name, process in processes:
      retcode = process.poll() # retcode should be 0 so test it against None
      if retcode is not None:
        print("LOADER: %s exited with %d" % (proc_name, retcode))
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
          print("LOADER: %s.%s closed." % (proc_name, pipe_name))
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
        print("LOADER: %s.%s closed." % (proc_name, pipe_name))
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
    sys.stderr.write('restore_volume.py <source> <destdev>\n  source: URL\n  destdev: device file\n')
    sys.exit(1)
    pass
    
  load_disk(sys.argv[1], sys.argv[2])
  pass
