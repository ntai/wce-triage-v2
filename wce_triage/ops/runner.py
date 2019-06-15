#
# Disk operations
#
# Tasks: each task is a disk operation. Some tasks can take a long time.
#
# For example, a task is like mkfs. As the task runs, it should produce progress
#
# By calling into diskop, it creates the plan - which is the sequence of tasks.
# exec runs through the tasks.
#

import datetime, re, subprocess
from enum import Enum

class RunState(Enum):
  Initial = 0
  Prepare = 1
  Preflight = 2
  Running = 3
  Success = 4
  Failuer = 5
  pass

#
# Base class for runner
#
class Runner:
  def __init__(self, ui):
    self.state = RunState.Initial
    self.ui = ui
    self.tasks = []
    pass

  def prepare(self):
    if self.state != RunState.Initial:
      raise Exception("Run state is not initial")
    self.state = RunState.Prepare
    pass


  def preflight(self):
    if self.state != RunState.Prepare:
      raise Exception("Run state is not Prepare")

    self.state = RunState.Preflight
    self.total_estimate_time = 0
    for task in self.tasks:
      self.total_estimate_time + task.estimate_time()
      pass
    self.ui.report_tasks(self.total_estimate_time, self.tasks)
    pass

  def report_failure(self, task):
    print("%s failed." % task.description)
    pass

  # Explaining what's going to happen
  def explain(self):
    step = 0
    for task in self.tasks:
      step = step + 1
      self.ui.print( "%d: %s %s" % (step, task.description, task.explain()))
      pass
    pass
  
  #
  def run(self):
    if self.state != RunState.Preflight:
      raise Exception("Run state is not Preflight")
    self.state = RunState.Running

    self.start_time = datetime.datetime.now()
    task = None
    while self.tasks:
      task = self.tasks[0]
      self.tasks = self.tasks[1:]

      task.start()

      while task.progress < 100:
        task.poll()
        pass

      if task.progress > 100:
        # something went wrong.
        break
      task = None

      self.current_time = datetime.datetime.now()
      self.elapsed_time = self.current_time - self.start_time
      pass

    # When the task completes, it is set to None.
    # If task is set, it's pointing to the task that stopped the
    # running.
    if task:
      self.state = RunState.Failure
      self.report_failure(task)
      pass
    else:
      self.state = RunState.Success
      pass
    pass

  pass
