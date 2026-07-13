import shlex
import signal
import threading
import traceback
from queue import SimpleQueue
from typing import Callable, Optional, TypedDict
import subprocess
import logging
from ..view import ConsoleView
from .process_pipe_reader import ProcessPipeReader
from ..models import ModelDispatch, Model
from ..messages import UserMessages, ErrorMessages
from ...lib import get_triage_logger
from ...ops.protocol import OperationProgress
import json


class ProcessRunnerMeta(TypedDict, total=False):
  """Keys read from ProcessRunner.meta: "tag" labels the process for
  logging/reporting (defaults to "process"); "result" is an optional
  callback invoked with the finished Popen once the process exits."""
  tag: str
  result: Callable[[Optional[subprocess.Popen]], None]


class ProcessRunner(threading.Thread):
  process: Optional[subprocess.Popen]
  stdout_dispatch: ModelDispatch
  stderr_dispatch: ModelDispatch
  meta: ProcessRunnerMeta
  _queue: SimpleQueue
  logger: logging.Logger
  stdout: ProcessPipeReader
  stderr: ProcessPipeReader

  @classmethod
  def class_name(cls):
    return "process_runner"

  def __init__(self,
               stdout_dispatch: Optional[ModelDispatch] = None,
               stderr_dispatch: Optional[ModelDispatch] = None,
               meta: Optional[ProcessRunnerMeta] = None):
    super().__init__(name=f"{self.class_name()}")
    # when model/model_dispatch is not given, stub is created.
    self.stdout_dispatch = stdout_dispatch if stdout_dispatch else ModelDispatch(Model())
    self.stderr_dispatch = stderr_dispatch if stderr_dispatch else ModelDispatch(Model())
    self.meta = ProcessRunnerMeta(**meta) if meta else ProcessRunnerMeta()
    self._queue = SimpleQueue()
    self.logger = get_triage_logger()
    self._kill_count = 0
    pass

  def queue(self, args: list, context: dict):
    self._queue.put((args, context))
    pass

  def dequeue(self):
    return self._queue.get()

  def run(self):
    while True:
      args, context = self.dequeue()
      if not args:
        break
      self.run_process(self.meta.get("tag", "process"), args, context, self.meta.get("result"))
      pass
    pass

  def error_message(self, message):
    self.logger.info(message)
    UserMessages.note(message)
    pass

  def run_process(self, tag, args, context, result):
    self.logger.info("Start process: " + shlex.join(args))
    try:
      self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
      self.error_message("%s is not found." % args[0])
      return
    except Exception as exc:
      self.error_message("%s is not found." % args[0])
      return

    self.stdout_dispatch.start(tag, context)
    self.stderr_dispatch.start(tag, context)

    self.stdout = ProcessPipeReader(self.process, self.process.stdout, dispatch=self.stdout_dispatch, tag=tag,
                                    name=f"{self.class_name()}-stdout-{tag}")
    self.stderr = ProcessPipeReader(self.process, self.process.stderr, dispatch=self.stderr_dispatch, tag=tag,
                                    name=f"{self.class_name()}-stderr-{tag}")

    self.stdout.start()
    self.stderr.start()

    try:
      self.process.wait()
      pass
    except Exception as exc:
      self.error_message("%s: %s" % (tag, traceback.format_exc()))
      pass

    if self.process:
      cmd = shlex.join(args)
      if self.process.returncode == -15:
        self.error_message("Process '%s' killed", cmd)
        self.logger.info("Process '%s' killed." % cmd)
      elif self.process.returncode != 0:
        self.error_message("Process '%s' failed with error code %d" % (cmd, self.process.returncode))
        self.logger.warning("Process '%s' failed with error code %d", cmd, self.process.returncode)
        pass
      pass
    else:
      self.error_message("Process is gone")
      pass

    self.stdout.join()
    self.stderr.join()

    self.stdout_dispatch.end(tag, context)
    self.stderr_dispatch.end(tag, context)

    self.process_ended(result)
    self.process = None
    pass

  def process_ended(self, result):
    if result:
      result(self.process)
      pass
    pass

  def is_process_running(self):
    # FIXME: this needs to be more accurate
    return self.process and self.process.returncode is None

  def terminate(self):
    if not self.is_process_running():
      return
    self._kill_count += 1
    if self._kill_count > 2:
      self.process.kill()
    elif self._kill_count > 1:
      self.process.terminate()
    else:
      self.process.send_signal(signal.SIGINT)
      pass
    pass

  pass


class SimpleProcessRunner(ProcessRunner):
  def __init__(self,
               stdout_dispatch: Optional[ModelDispatch] = None,
               stderr_dispatch: Optional[ModelDispatch] = ErrorMessages,
               meta: Optional[ProcessRunnerMeta] = None):
    super().__init__(stdout_dispatch, stderr_dispatch, meta)
    pass
  pass


class RunnerOutputDispatch(ModelDispatch):
  """ops/runner + json_ui output dispatch. Every report is a complete,
  self-sufficient OperationProgress (report/device/runStatus/runMessage/
  runEstimate/runTime/tasks) - there's no delta to reconstruct, unlike the
  old per-step "task" + "step" patching this used to need."""
  def dispatch(self, update):
    try:
      json_data = json.loads(update)
    except Exception:
      get_triage_logger().debug(update)
      raise Exception("not json")
    if json_data.get("event") == "message":
      # Side-band log line from json_ui.log() (e.g. a task's exception
      # traceback) - not an OperationProgress report. Surface it the same
      # way UserMessages does, via the 'message' socket event Messages.tsx
      # listens on, instead of validating it as OperationProgress.
      UserMessages.note(json_data["message"]["message"])
      return
    message = OperationProgress.model_validate(json_data["message"])
    super().dispatch(message.model_dump(mode="json"))
    pass
  pass


class JsonOutputDispatch(ModelDispatch):
  """json output dispatch: the output of process is JSON string and store it as is."""

  def dispatch(self, update):
    """Parse the output string as json and dispatch to the model."""
    json_data = None
    try:
      json_data = json.loads(update)
    except:
      pass
    if json_data:
      # json_data["event"] should match with the event.
      super().dispatch(json_data)
    else:
      get_triage_logger().debug(update)
      raise Exception("not json")
      pass
    pass
  pass


if __name__ == "__main__":
  view = ConsoleView()
  stdout = UserMessages
  stderr = ErrorMessages
  stdout.set_view(view)
  stderr.set_view(view)
  pr = ProcessRunner(stdout_dispatch=stdout, stderr_dispatch=stderr, meta=ProcessRunnerMeta(tag="test"))
  pr.start()
  # pr.queue.put(["/bin/sh", "-c", "echo Hello, world 1"])
  # pr.queue.put(["/bin/sh", "echo Hello, world 2"])
  # pr.queue.put(["/bin/foobar", "echo Hello, world 2"])
  context = {"job": "test"}
  pr.queue(["stdbuf", "-oL", "fixture/slow.sh"], context)
  pr.queue(None, context)
  pr.join()
  print(stdout.model.data)
  print(stderr.model.data)
  print(UserMessages.model.data)
