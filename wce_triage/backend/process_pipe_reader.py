import threading
from collections import deque
import subprocess
import io
from typing import Optional
from wce_triage.backend.models import Model, ModelDispatch


class ProcessPipeReader(threading.Thread):
  proc: subprocess.Popen
  pipe: io.BytesIO
  dispatch: Optional[ModelDispatch]

  def __init__(self, proc:subprocess.Popen, pipe: io.BytesIO,
               dispatch=None,
               tag=None, encoding='iso-8859-1'):
    super().__init__()
    self.encoding = encoding
    self.alive = True
    self.proc = proc
    self.pipe = pipe # process pipe stream, not the pipe
    self.fragments = deque()
    self.lines = []
    self.tag = tag
    self.dispatch = dispatch
    pass

  def run(self):
    while self.alive:
      incoming = self.pipe.read1()
      if incoming == b'':
        # Pipe is closed.
        self.alive = False
        self._flush_fragments()
      else:
        for ch in incoming:
          if ch in [ord('\r'), ord('\n')]:
            self._flush_fragments()
            pass
          else:
            self.fragments.append(ch)
            pass
          pass
        pass
      pass
    pass

  def reading(self):
    return self.pipe if self.alive else None

  def readline(self):
    line = None
    if len(self.lines) > 0:
      line = self.lines[0]
      self.lines = self.lines[1:]
      pass
    return line

  def _flush_fragments(self):
    if len(self.fragments) == 0:
      return
    buffer = bytearray(len(self.fragments) + 1)
    for i in range(len(self.fragments)):
      buffer[i] = self.fragments[i]
      pass
    buffer[len(self.fragments)] = ord(b'\n')
    self.fragments.clear()
    self.handle_line(buffer.decode(self.encoding))
    pass

  def handle_line(self, line):
    if self.dispatch:
      self.dispatch.dispatch(line)
    else:
      self.lines.append(line)
      pass
    pass
  pass

