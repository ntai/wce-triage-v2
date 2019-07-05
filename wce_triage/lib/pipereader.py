
from collections import deque
import subprocess, sys

class PipeReader:
  def __init__(self, pipe, encoding='iso-8859-1'):
    self.encoding = encoding
    self.pipe = pipe
    self.fragments = deque()
    pass
  
  def reading(self):
    return self.pipe is not None

  def readline(self):
    if self.pipe is None:
      return b''

    # it's painful to read one at a time but any other way seems to block.
    ch = self.pipe.read(1) # oh so C
    if ch == b'':
      # Pipe is closed. You better take care of closed pipe.
      # returning b'' is such an ugly hack. For more sane people,
      # throwing exception is neater.
      self.pipe = None
      return b''
    else:
      if ch in [ b'\n', b'\r']:
        buffer = bytearray(len(self.fragments)+1)
        for i in range(len(self.fragments)):
          buffer[i] = ord(self.fragments[i])
          pass
        buffer[len(self.fragments)] = ord(b'\n')
        self.fragments.clear()
        return buffer.decode(self.encoding)
      else:
        self.fragments.append(ch)
        return None
      pass
    pass
  pass

  
if __name__ == "__main__":
  # what a convoluted way to do a simple thing...
  cat = subprocess.Popen( 'cat /etc/hosts', shell=True, stdout=subprocess.PIPE)
  reader = PipeReader(cat.stdout)
  while reader.reading():
    chunk = reader.readline()
    if chunk == b'':
      break
    if chunk != None:
      sys.stdout.write(chunk)
      pass
    pass
  pass