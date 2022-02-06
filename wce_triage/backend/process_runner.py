import threading
import time
import traceback
from queue import SimpleQueue, Queue
from typing import Optional
import subprocess
import logging
from wce_triage.backend.view import ConsoleView
from .process_pipe_reader import ProcessPipeReader
from .models import ModelDispatch
from .messages import UserMessages
from ..lib.util import get_triage_logger


class ProcessRunner(threading.Thread):
  process: subprocess.Popen
  stdout_dispatch: Optional[ModelDispatch]
  stderr_dispatch: Optional[ModelDispatch]
  meta: dict
  _queue: SimpleQueue
  logger: logging.Logger
  stdout: ProcessPipeReader
  stderr: ProcessPipeReader

  def __init__(self,
               stdout_dispatch: Optional[ModelDispatch],
               stderr_dispatch: Optional[ModelDispatch],
               meta):
    super().__init__()
    self.stdout_dispatch = stdout_dispatch
    self.stderr_dispatch = stderr_dispatch
    self.meta = meta
    self._queue = SimpleQueue()
    self.logger = get_triage_logger()
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
      self.run_process(self.meta.get("tag", "process"), args, context)
      pass
    pass

  def error_message(self, message):
    self.logger.info(message)
    UserMessages.note(message)
    pass

  def run_process(self, tag, args, context):
    try:
      self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
      self.error_message("%s is not found." % args[0])
      return
    except Exception as exc:
      self.error_message("%s is not found." % args[0])
      return

    self.stdout_dispatch.start(tag, context)
    self.stderr_dispatch.start(tag, context)

    self.stdout = ProcessPipeReader(self.process, self.process.stdout, dispatch=self.stdout_dispatch)
    self.stderr = ProcessPipeReader(self.process, self.process.stderr, dispatch=self.stderr_dispatch)

    self.stdout.start()
    self.stderr.start()

    try:
      while self.process.returncode is None:
        self.process.poll()
        time.sleep(1)
        pass
      pass
    except Exception as exc:
      self.error_message("%s: %s" % (tag, traceback.format_exc()))
      pass

    if self.process.returncode != 0:
      self.error_message("Process '%s' failed with error code %d" % (" ".join(args), self.process.returncode))
      pass

    self.stdout.join()
    self.stderr.join()

    self.stdout_dispatch.end(tag, context)
    self.stderr_dispatch.end(tag, context)
    self.process = None
    pass

  def is_process_running(self):
    # FIXME: this needs to be more accurate
    return self.process and self.process.returncode is None

  def terminate(self):
    if not self.is_process_running():
      return
    process = self.process
    self.process = None
    process.terminate()
    pass

  pass


class SimpleProcessRunner(ProcessRunner):
  def __init__(self,
               stdout_dispatch: Optional[ModelDispatch] = None,
               stderr_dispatch: Optional[ModelDispatch] = UserMessages,
               meta={}):
    super().__init__(stdout, stderr, meta)
    pass
  pass


if __name__ == "__main__":
  view = ConsoleView()
  stdout = UserMessages
  stderr = MessageDispatch(MessagesModel())
  stdout.set_view(view)
  stderr.set_view(view)
  pr = ProcessRunner(stdout, stderr, {"tag": "test"})
  pr.start()
  # pr.queue.put(["/bin/sh", "-c", "echo Hello, world 1"])
  # pr.queue.put(["/bin/sh", "echo Hello, world 2"])
  # pr.queue.put(["/bin/foobar", "echo Hello, world 2"])
  pr.queue.put(["stdbuf", "-oL", "fixture/slow.sh"])
  pr.queue.put(None)
  pr.join()
  print(stdout.model.data)
  print(stderr.model.data)
  print(UserMessages.model.data)
