
from collections import deque
import subprocess, sys, asyncio
from wce_triage.lib.util import *
import functools


tlog = get_triage_logger()

class PipeReader:
  def __init__(self, pipe, tag=None, encoding='iso-8859-1'):
    self.encoding = encoding
    self.alive = True
    self.pipe = pipe
    self.fragments = deque()
    self.tag = tag

    # a bit of a hack. This is about asyncio's add_reader is done or not
    self.asyncio_reader = True
    pass

  def add_to_event_loop(pipe, callback, tag):
    asyncio.get_event_loop().add_reader(pipe, functools.partial(callback, PipeReader(pipe, tag=tag)))
    pass
  
  def remove_from_event_loop(self):
    if self.asyncio_reader:
      self.asyncio_reader = False
      asyncio.get_event_loop().remove_reader(self.pipe)
      pass
    pass
  

  def reading(self):
    return self.pipe if self.alive else None

  def readline(self):
    if not self.alive:
      return b''

    # it's painful to read one at a time but any other way seems to block.
    ch = self.pipe.read(1) # oh so C
    if ch == b'':
      # Pipe is closed. 
      self.alive = False
      return self._flush_fragments()
    else:
      if ch in [ b'\n', b'\r']:
        return self._flush_fragments()
      else:
        self.fragments.append(ch)
        return None
      pass
    pass

  def _flush_fragments(self):
    buffer = bytearray(len(self.fragments)+1)
    for i in range(len(self.fragments)):
      buffer[i] = ord(self.fragments[i])
      pass
    buffer[len(self.fragments)] = ord(b'\n')
    self.fragments.clear()
    return buffer.decode(self.encoding)

  def flush(self):
    return self._flush_fragments()

  pass

  
if __name__ == "__main__":
  # what a convoluted way to do a simple thing...
  cat = subprocess.Popen( 'cat /etc/hosts', shell=True, stdout=subprocess.PIPE)
  reader = PipeReader(cat.stdout)
  while reader.reading():
    chunk = reader.readline()
    if chunk == b'':
      break
    if chunk is not None:
      sys.stdout.write(chunk)
      pass
    pass
  pass
