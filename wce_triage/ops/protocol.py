#
# Shared NDJSON wire types exchanged between wce_triage.bin worker processes
# and the ops/ runner & task classes that drive them.
#
# Two protocol layers live here:
#
# - ProgressReport / OpticalTestResult: one-shot "here's my status" objects
#   emitted by copy/wipe/test tools (fanout_copy, multiwipe, binarycopy,
#   test_optical), wrapped in an envelope ({"event": ..., "message": ...}).
#
# - DriverEvent: the lower-level per-line events emitted by process_driver.py
#   while it drives one or more native subprocesses (partclone, rsync, wget,
#   curl). The subprocess's own textual progress output is carried verbatim
#   in `line` - we don't parse partclone/rsync's own format here, only frame
#   it so the consumer doesn't have to regex a "name: proc.stream:text" prefix.
#
from __future__ import annotations

import datetime
import sys
from enum import Enum
from typing import List, Literal, Optional, TextIO, Tuple

from pydantic import BaseModel, ConfigDict

from .run_state import RunState


def emit_line(payload: BaseModel, stream: TextIO = sys.stdout) -> None:
  """Write one NDJSON line for payload and flush immediately."""
  print(payload.model_dump_json(exclude_none=True), file=stream, flush=True)
  pass


def split_lines(buffer: str) -> Tuple[List[str], str]:
  """Split a growing text buffer into complete lines and the remainder.
  Consumers keep accumulating subprocess stdout/stderr into a string; this
  replaces the repeated "find('\\n')" loop used to peel off complete lines."""
  lines = buffer.split("\n")
  return lines[:-1], lines[-1]


#
# Progress reports for copy/wipe style tools (fanout_copy, multiwipe, binarycopy)
#
class ProgressReport(BaseModel):
  """Progress of a copy/wipe operation, keyed by which destination/device it concerns."""
  key: str
  runStatus: RunState
  runMessage: str
  progress: int = 0                        # 0-100, or 999 sentinel meaning failed (matches op_task's own convention)
  runTime: float = 0
  runEstimate: float = 0
  totalBytes: Optional[int] = None
  remainingBytes: Optional[int] = None
  totalSectors: Optional[int] = None
  writtenSectors: Optional[int] = None
  remainingSectors: Optional[int] = None
  destination: Optional[str] = None
  startTime: Optional[datetime.datetime] = None
  currentTime: Optional[datetime.datetime] = None
  verdict: Optional[str] = None
  pass


class ProgressEnvelope(BaseModel):
  event: str
  message: ProgressReport
  pass


#
# test_optical.py's result report
#
class OpticalTestResult(BaseModel):
  component: str
  result: bool
  device: str
  runMessage: str
  verdict: List[str] = []
  elapseTime: Optional[float] = None
  pass


class OpticalEnvelope(BaseModel):
  event: str
  message: OpticalTestResult
  pass


#
# process_driver.py's per-line events, replacing the old
# "<bin_name>: <proc>.<pipetag>:<text>" plain-text framing.
#
class DriverEventType(str, Enum):
  start = "start"      # a child process was launched
  line = "line"         # one line of output from a child's stdout/stderr
  error = "error"       # a child exited non-zero, or the driver hit an internal error
  exit = "exit"         # a child exited (cleanly)
  pass


class DriverEvent(BaseModel):
  type: DriverEventType
  proc: str                                # process name, e.g. "partclone", "wget", "rsync"
  stream: Optional[str] = None             # "stdout" | "stderr", set when type is "line"
  pid: Optional[int] = None
  line: Optional[str] = None               # raw text, verbatim from the child process
  returncode: Optional[int] = None
  pass


#
# ops/runner.py + ops/json_ui.py's progress protocol: the overall status of a
# Runner plus the status of every task it holds. Sent whole on every report -
# there is exactly one machine involved (the disk being rewritten IS the
# server), so there is no reason to send only a delta and reconstruct state
# on the receiving end.
#
TaskState = Literal["waiting", "running", "done", "fail"]


class TaskStatus(BaseModel):
  """Describes one op_task (or, for a task representing several parallel
  subprocess targets, one of its describe_subtasks() entries)."""
  step: int
  taskCategory: str
  taskProgress: float                      # 0-100, or 999 sentinel meaning failed
  taskEstimate: float
  taskElapse: float
  taskStatus: TaskState
  taskMessage: Optional[str] = None
  taskExplain: str
  taskVerdict: List[str] = []

  model_config = ConfigDict(from_attributes=True)
  pass


ReportKind = Literal["tasks", "task_progress", "task_success", "task_failure", "run_progress"]


class OperationProgress(BaseModel):
  """Overall status of a runner (save/load/sync/wipe) plus the status of every task it holds."""
  report: ReportKind
  device: str                              # runner_id, usually a disk device name
  runStatus: RunState
  runMessage: str
  runEstimate: float = 0
  runTime: float = 0
  step: Optional[int] = None               # which task just changed, informational only
  tasks: List[TaskStatus] = []

  model_config = ConfigDict(from_attributes=True)
  pass


class OperationEnvelope(BaseModel):
  event: str
  message: OperationProgress

  model_config = ConfigDict(from_attributes=True)
  pass


def idle_operation_progress(device: str = "") -> OperationProgress:
  """The 'nothing has run yet' placeholder for a load/save/sync/wipe status endpoint."""
  return OperationProgress(report="tasks", device=device, runStatus=RunState.Initial,
                            runMessage="", tasks=[]).model_dump(mode="json")
