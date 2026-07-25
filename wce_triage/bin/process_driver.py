#
# Probably, I need to deal with signals. That's gonna be future project.
#
import os, sys, traceback, datetime
import queue
import threading

if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

from ..lib.util import get_triage_logger
from ..lib.pipereader import PipeReader
from ..ops.protocol import DriverEvent, DriverEventType, emit_line
import signal


tlog = get_triage_logger()

from collections import namedtuple
PipeInfo = namedtuple('PipeInfo', 'app, process, pipetag, pipe')


def _terminate_all(processes):
  for proc_name, process in processes:
    process.terminate()
    pass
  pass


class DriverEmitter:
  """Emits process_driver's per-line events as NDJSON (DriverEvent) on stderr,
  replacing the old '<name>: <proc>.<pipetag>:<text>' plain-text framing.

  All emission happens on a dedicated writer thread. emit_line() does a
  blocking print() to our stderr, which is itself a pipe back to our parent -
  if the parent falls behind draining it, that write can block. Running it on
  its own thread means a stalled write can never block the pipe-reader/process-
  waiter threads that feed it, which is what previously caused exited
  subprocesses to go unnoticed. start/exit/error events are queued and always
  delivered, in order; line (progress) events are coalesced by (proc, stream)
  key - if the writer thread falls behind, only the latest value for a key
  survives, which is safe because progress lines are monotonic snapshots
  (confirmed by every consumer of this stream treating a "line" event as an
  overwrite, never an accumulation).
  """

  WRITER_POLL_INTERVAL = 0.1

  def __init__(self, stream=None):
    self._stream = stream if stream is not None else sys.stderr
    self._important = queue.Queue()
    self._latest_lines = {}
    self._lines_lock = threading.Lock()
    self._wake = threading.Event()
    self._stop = threading.Event()
    self._thread = threading.Thread(target=self._writer_loop, daemon=True, name="DriverEmitter")
    self._thread.start()
    pass

  def start(self, proc, pid):
    tlog.debug("%s PID=%d start" % (proc, pid))
    self._enqueue(DriverEvent(type=DriverEventType.start, proc=proc, pid=pid))
    pass

  def line(self, proc, stream, text):
    text = text.strip()
    if not text:
      return
    tlog.debug("%s.%s: %s" % (proc, stream, text))
    event = DriverEvent(type=DriverEventType.line, proc=proc, stream=stream, line=text)
    with self._lines_lock:
      self._latest_lines[proc + "." + stream] = event
      pass
    self._wake.set()
    pass

  def exit(self, proc, pid, returncode):
    tlog.debug("%s PID=%s exited with %s" % (proc, pid, returncode))
    self._enqueue(DriverEvent(type=DriverEventType.exit, proc=proc, pid=pid, returncode=returncode))
    pass

  def error(self, proc, text, pid=None):
    text = text.strip()
    if not text:
      return
    for one_line in text.split('\n'):
      if not one_line:
        continue
      tlog.debug("%s.ERROR: %s" % (proc, one_line))
      self._enqueue(DriverEvent(type=DriverEventType.error, proc=proc, pid=pid, line=one_line))
      pass
    pass

  def close(self):
    """Flush all pending events and stop the writer thread. Call once, after
    all processes have been reaped, before the process exits - this is what
    guarantees buffered exit/error events actually reach the parent. Blocks
    until the writer thread has actually drained everything: a bounded
    timeout here would let a caller race a still-draining writer thread
    (both touching self._important/self._latest_lines), and would silently
    return before real data was flushed if the consumer was simply slow
    rather than truly stuck."""
    self._stop.set()
    self._wake.set()
    self._thread.join()
    pass

  def _enqueue(self, event):
    self._important.put(event)
    self._wake.set()
    pass

  def _writer_loop(self):
    while True:
      self._wake.wait(timeout=self.WRITER_POLL_INTERVAL)
      self._wake.clear()
      self._drain()
      if self._stop.is_set() and self._important.empty() and not self._latest_lines:
        break
      pass
    pass

  def _drain(self):
    while True:
      try:
        event = self._important.get_nowait()
      except queue.Empty:
        break
      emit_line(event, stream=self._stream)
      pass

    with self._lines_lock:
      pending, self._latest_lines = self._latest_lines, {}
      pass
    for event in pending.values():
      emit_line(event, stream=self._stream)
      pass
    pass
  pass


class _DriverState:
  """Coordinates the still-running process list across reader/waiter threads.

  Reader threads only ever call printer.line()/error(); waiter threads are
  the ones that need to remove their process from the running set, decide
  whether a bad exit should trigger _terminate_all() on the rest, and notice
  when the last process is gone - all of which touch this shared list from
  multiple threads at once, hence the lock.
  """

  def __init__(self, processes):
    self._lock = threading.Lock()
    self._processes = list(processes)
    self.retcode = 0
    self.all_done = threading.Event()
    # Only set once someone actually asks the pipeline to stop (a signal, or
    # one process failing and taking the rest down with it) - this is what
    # lets drive_process() tell "still legitimately running" apart from
    # "asked to stop and not responding", so a multi-minute copy isn't
    # mistaken for a hang.
    self.terminate_requested = threading.Event()
    if not self._processes:
      self.all_done.set()
      pass
    pass

  def process_exited(self, proc_name, process, returncode):
    with self._lock:
      try:
        self._processes.remove((proc_name, process))
      except ValueError:
        pass
      # Keep the first failure's code - it names the process that actually
      # failed. Processes torn down afterwards by _terminate_all() below
      # exit with their own (e.g. -15) code, which would otherwise overwrite
      # it depending on reap order.
      if returncode != 0 and self.retcode == 0:
        self.retcode = returncode
        self.terminate_requested.set()
        _terminate_all(self._processes)
        pass
      done = not self._processes
      pass
    if done:
      self.all_done.set()
      pass
    pass

  def terminate_all(self):
    with self._lock:
      self.terminate_requested.set()
      _terminate_all(self._processes)
      pass
    pass
  pass


class _PipeReaderThread(threading.Thread):
  """Reads one child pipe to completion on its own thread.

  PipeReader.readline() blocks on a real 1-byte read() syscall (see
  lib/pipereader.py - do not change that to a chunked read, it breaks live
  progress reporting for partclone/wget's \\r-terminated status lines), so
  there is no polling here: the thread just blocks until a line is ready or
  the pipe closes, exactly like the old select.poll()-driven loop did, minus
  the fd bookkeeping needed to multiplex several pipes on one thread.
  """

  def __init__(self, proc_name, pipetag, pipe, printer):
    super().__init__(daemon=True, name="PipeReader-%s.%s" % (proc_name, pipetag))
    self._proc_name = proc_name
    self._pipetag = pipetag
    self._pipe = pipe
    self._printer = printer
    pass

  def run(self):
    reader = PipeReader(self._pipe, tag=self._proc_name + "." + self._pipetag)
    try:
      while True:
        line = reader.readline()
        if line == b'':
          break
        if line is not None:
          self._printer.line(self._proc_name, self._pipetag, line)
          pass
        pass
      pass
    except Exception:
      self._printer.error(self._proc_name, "pipe reader failed: %s" % traceback.format_exc())
    finally:
      try:
        self._pipe.close()
      except OSError:
        pass
      pass
    pass
  pass


class _ProcessWaiterThread(threading.Thread):
  """Blocks on one child's exit via process.wait() - a real blocking wait,
  not a poll. This also retires a whole class of bug the old poll()-based
  loop needed a workaround for: process.wait() cannot "miss" an exit the way
  a periodic process.poll() call could, so the old os.kill(pid, 0) fallback
  check (for an exit poll() failed to notice) is no longer needed."""

  def __init__(self, proc_name, process, printer, state):
    super().__init__(daemon=True, name="ProcessWaiter-%s" % proc_name)
    self._proc_name = proc_name
    self._process = process
    self._printer = printer
    self._state = state
    pass

  def run(self):
    try:
      returncode = self._process.wait()
    except Exception:
      self._printer.error(self._proc_name, "wait() failed: %s" % traceback.format_exc(), pid=self._process.pid)
      self._state.process_exited(self._proc_name, self._process, -1)
      return
    self._printer.exit(self._proc_name, self._process.pid, returncode)
    self._state.process_exited(self._proc_name, self._process, returncode)
    pass
  pass


#
# Probably it's better to make this to a class...
#
def drive_process(name, processes, pipes):
  printer = DriverEmitter()
  state = _DriverState(processes)

  def handler_stop_signals(signum, frame):
    '''propagate terminate signal to children'''
    state.terminate_all()
    pass

  signal.signal(signal.SIGINT, handler_stop_signals)
  signal.signal(signal.SIGTERM, handler_stop_signals)

  reader_threads = [_PipeReaderThread(pipeinfo.app, pipeinfo.pipetag, pipeinfo.pipe, printer)
                     for pipeinfo in pipes]

  waiter_threads = []
  for proc_name, process in processes:
    printer.start(proc_name, process.pid)
    waiter_threads.append(_ProcessWaiterThread(proc_name, process, printer, state))
    pass

  for thread in reader_threads + waiter_threads:
    thread.start()
    pass

  # Wait for every process to be reaped. This is unbounded as long as things
  # are running normally - a multi-minute partclone/rsync copy is not a hang
  # - only once terminate_requested fires (a signal, or one process's failure
  # cascading to the rest) do we start a bounded grace period, matching the
  # old code's 10 second window after a stop request for children to unwind
  # (e.g. partclone flushing its cache) before we give up on them.
  grace_period = 10
  terminate_deadline = None
  while not state.all_done.wait(timeout=1):
    if state.terminate_requested.is_set():
      if terminate_deadline is None:
        terminate_deadline = datetime.datetime.now() + datetime.timedelta(seconds=grace_period)
      elif datetime.datetime.now() >= terminate_deadline:
        tlog.error("%s: processes still running %ds after termination, giving up." % (name, grace_period))
        state.retcode = state.retcode or -1
        break
      pass
    pass

  for thread in waiter_threads:
    thread.join(timeout=5)
    pass
  for thread in reader_threads:
    thread.join(timeout=5)
    pass

  # Guarantee buffered exit/error events actually reach the parent before we
  # exit - that's the whole point of this tool.
  printer.close()
  return state.retcode
