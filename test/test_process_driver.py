import json
import subprocess
import sys
import threading
import time
import unittest

from wce_triage.bin.process_driver import DriverEmitter, PipeInfo, drive_process


class RecordingStream:
  """Thread-safe stand-in for sys.stderr that records each write() call."""

  def __init__(self):
    self._lock = threading.Lock()
    self.chunks = []
    pass

  def write(self, data):
    with self._lock:
      self.chunks.append(data)
      pass
    pass

  def flush(self):
    pass

  def events(self):
    with self._lock:
      chunks = list(self.chunks)
      pass
    return [json.loads(chunk) for chunk in chunks if chunk.strip()]


class SlowStream(RecordingStream):
  """Like RecordingStream, but every write() blocks for a bit - simulates a
  parent that's slow to drain the pipe, the exact condition that used to
  freeze drive_process()'s read/reap loop."""

  def __init__(self, delay):
    super().__init__()
    self.delay = delay
    pass

  def write(self, data):
    time.sleep(self.delay)
    super().write(data)
    pass


class Test_driver_emitter(unittest.TestCase):

  def test_start_exit_error_always_delivered(self):
    stream = RecordingStream()
    emitter = DriverEmitter(stream=stream)
    for i in range(20):
      emitter.start("proc%d" % i, 1000 + i)
      pass
    for i in range(20):
      emitter.exit("proc%d" % i, 1000 + i, 0)
      pass
    emitter.error("proc0", "line one\nline two")
    emitter.close()

    events = stream.events()
    starts = [e for e in events if e["type"] == "start"]
    exits = [e for e in events if e["type"] == "exit"]
    errors = [e for e in events if e["type"] == "error"]
    self.assertEqual(len(starts), 20)
    self.assertEqual(len(exits), 20)
    self.assertEqual(len(errors), 2)
    pass

  def test_line_events_coalesce_to_latest_value(self):
    stream = RecordingStream()
    emitter = DriverEmitter(stream=stream)
    # Fire far faster than WRITER_POLL_INTERVAL so the writer thread cannot
    # possibly keep up - only the latest value for the key should survive.
    for pct in range(100):
      emitter.line("rsync", "stdout", "progress %d%%" % pct)
      pass
    emitter.close()

    events = stream.events()
    lines = [e for e in events if e["type"] == "line"]
    self.assertEqual(len(lines), 1)
    self.assertEqual(lines[0]["line"], "progress 99%")
    pass

  def test_distinct_keys_are_not_coalesced_together(self):
    stream = RecordingStream()
    emitter = DriverEmitter(stream=stream)
    emitter.line("rsync-a", "stdout", "a progress")
    emitter.line("rsync-b", "stdout", "b progress")
    emitter.close()

    events = stream.events()
    lines = {e["proc"]: e["line"] for e in events if e["type"] == "line"}
    self.assertEqual(lines, {"rsync-a": "a progress", "rsync-b": "b progress"})
    pass

  def test_calls_never_block_even_with_slow_consumer(self):
    stream = SlowStream(delay=0.05)
    emitter = DriverEmitter(stream=stream)

    started = time.monotonic()
    for i in range(10):
      emitter.start("proc%d" % i, 1000 + i)
      emitter.exit("proc%d" % i, 1000 + i, 0)
      pass
    elapsed = time.monotonic() - started
    # These calls only enqueue work for the writer thread; they must return
    # essentially immediately even though the writer thread is stuck doing
    # slow writes. This is the core regression test: previously, drive_
    # process()'s single thread did the equivalent of these blocking writes
    # itself, which could freeze its process.poll() reaping loop entirely.
    self.assertLess(elapsed, 0.2)

    emitter.close()
    events = stream.events()
    self.assertEqual(len([e for e in events if e["type"] == "start"]), 10)
    self.assertEqual(len([e for e in events if e["type"] == "exit"]), 10)
    pass

  def test_close_flushes_pending_events_before_returning(self):
    stream = RecordingStream()
    emitter = DriverEmitter(stream=stream)
    emitter.start("proc", 42)
    emitter.exit("proc", 42, 0)
    emitter.close()
    events = stream.events()
    self.assertEqual([e["type"] for e in events], ["start", "exit"])
    pass


class Test_drive_process(unittest.TestCase):
  """Exercises drive_process() end to end with real subprocesses - the thread-
  per-pipe/thread-per-process design that replaced the old select.poll() loop.
  """

  def _run(self, specs):
    """specs: list of (proc_name, argv). Launches each with stdout+stderr
    piped, drives them, and returns (retcode, recorded events) with
    DriverEmitter's NDJSON captured instead of sent to the real stderr."""
    processes = []
    pipes = []
    for proc_name, argv in specs:
      proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      processes.append((proc_name, proc))
      pipes.append(PipeInfo(proc_name, proc, "stdout", proc.stdout))
      pipes.append(PipeInfo(proc_name, proc, "stderr", proc.stderr))
      pass

    stream = RecordingStream()
    old_stderr = sys.stderr
    sys.stderr = stream
    try:
      retcode = drive_process("TEST", processes, pipes)
    finally:
      sys.stderr = old_stderr
      pass
    return retcode, stream.events()

  def test_single_process_reports_start_line_and_exit(self):
    retcode, events = self._run([("echoer", ["sh", "-c", "echo hello world"])])
    self.assertEqual(retcode, 0)
    self.assertEqual(len([e for e in events if e["type"] == "start"]), 1)
    exits = [e for e in events if e["type"] == "exit"]
    self.assertEqual(exits, [{"type": "exit", "proc": "echoer", "pid": exits[0]["pid"], "returncode": 0}])
    lines = [e["line"] for e in events if e["type"] == "line"]
    self.assertIn("hello world", lines)
    pass

  def test_failing_process_terminates_siblings_and_keeps_first_retcode(self):
    # "sleeper" runs long enough that it can only have exited because
    # _terminate_all() reached it - if the driver failed to cascade the
    # termination, this test would hang for 30s instead of returning quickly.
    retcode, events = self._run([
      ("failer", ["sh", "-c", "exit 7"]),
      ("sleeper", ["sleep", "30"]),
    ])
    self.assertEqual(retcode, 7)
    exits = {e["proc"]: e["returncode"] for e in events if e["type"] == "exit"}
    self.assertEqual(exits["failer"], 7)
    self.assertIn("sleeper", exits)
    self.assertNotEqual(exits["sleeper"], 0)
    pass

  def test_two_clean_processes_both_reported(self):
    retcode, events = self._run([
      ("one", ["sh", "-c", "echo one-out"]),
      ("two", ["sh", "-c", "echo two-out"]),
    ])
    self.assertEqual(retcode, 0)
    exits = {e["proc"]: e["returncode"] for e in events if e["type"] == "exit"}
    self.assertEqual(exits, {"one": 0, "two": 0})
    lines = [e["line"] for e in events if e["type"] == "line"]
    self.assertIn("one-out", lines)
    self.assertIn("two-out", lines)
    pass


if __name__ == '__main__':
  unittest.main()
