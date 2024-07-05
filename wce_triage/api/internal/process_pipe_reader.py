import threading
from collections import deque
import subprocess
import io
from typing import Optional
from ..models import ModelDispatch
from ...lib import get_triage_logger


class ProcessPipeReader(threading.Thread):
  proc: subprocess.Popen
  pipe: io.BytesIO
  dispatch: Optional[ModelDispatch]
  big_buffer: bytearray

  def __init__(self, proc:subprocess.Popen, pipe: io.BytesIO,
               name="Unnamed PipeReader",
               dispatch=None,
               tag=None, encoding='iso-8859-1'):
    super().__init__(name=name)
    self.encoding = encoding
    self.alive = True
    self.proc = proc
    self.pipe = pipe # process pipe stream, not the pipe
    self.fragments = deque()
    self.lines = []
    self.tag = tag
    self.dispatch = dispatch

    self.big_buffer = bytearray(0)
    self.length = 0
    pass

  def run(self):
    while self.alive:
      incoming = self.pipe.read1()
      if incoming == b'':
        # Pipe is closed.
        self.alive = False
        self._flush_fragments()
      else:
        while len(incoming) > 0:
          bp0 = incoming.find(ord('\n'))
          bp1 = incoming.find(ord('\r'))
          if bp0 == -1:
            bp = bp1
          else:
            if bp1 == -1:
              bp = bp0
            else:
              bp = min(bp0, bp1)
              pass
            pass

          if bp >= 0:
            self.big_buffer = self.big_buffer + incoming[:bp] + b'\n'
            self._flush_fragments()
            incoming = incoming[bp + 1:]
            pass
          else:
            self.big_buffer = self.big_buffer + incoming
            break
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
    if len(self.big_buffer) == 0:
      return
    self.handle_line(self.big_buffer.decode(self.encoding))
    self.big_buffer.clear()
    pass

  def handle_line(self, line):
    tlog = get_triage_logger()
    tlog.debug("handle_line(%s): %s" % (self.tag, line))
    if self.dispatch:
      self.dispatch.dispatch(line)
    else:
      self.lines.append(line)
      pass
    pass
  pass

