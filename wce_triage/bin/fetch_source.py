#
# WIP:
# Getting the file list and size using curl
#
import os, sys, subprocess, urllib, datetime
from ..lib.util import *
from ..lib.timeutil import *
import urllib.parse

def get_directory(source):
  
  transport_scheme = get_transport_scheme(source)
  if transport_scheme:
    curl = subprocess.run([ "curl", "-q", "-s", "-l", source ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    fullpath = [ urllib.parse.urljoin(source, filename) for filename in curl.stdout.decode('utf-8').splitlines() ]
    print( fullpath)
    print(curl.stderr)
    pipe = os.pipe()
    curl = subprocess.run([ "curl", "-q", "-s", "-S", "-I"] + fullpath, stdout=pipe[1], stderr=pipe[1])
    output = bytearray(65536)
    os.set_blocking(pipe[0], False)
    reading = True
    while reading:
      try:
        bytes_read = os.readv(pipe[0], [output])
        print(bytes_read)
      except BlockingIOError:
        reading = False
        pass
      pass
    pass
  else:
    return []
  pass

if __name__ == "__main__":
  print(get_directory(sys.argv[1]))
  pass

