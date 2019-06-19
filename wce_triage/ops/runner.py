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

import datetime, re, subprocess, traceback
from ops.run_state import RunState
from lib.timeutil import *

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
    self.task_step = 0
    pass


  def preflight(self):
    if self.state != RunState.Prepare:
      raise Exception("Run state is not Prepare")

    # Tell the tasks I'm the runner.
    for task in self.tasks:
      task.runner = self
      pass

    self.state = RunState.Preflight
    self._update_total_time_estimate()
    self.ui.report_tasks(self.total_time_estimate, self.tasks)
    pass

  def _update_total_time_estimate(self):
    self.total_time_estimate = 0
    for task in self.tasks:
      self.total_time_estimate = self.total_time_estimate + task.estimate_time()
      pass
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
    while self.task_step < len(self.tasks):
      task = self.tasks[self.task_step]

      if self.state == RunState.Running or task.teardown_task:
        try:
          self._run_task(task, self.ui)
        except Exception as exc:
          self.state = RunState.Failed;
          self.ui.log("Task: " + task.description + "\n" + traceback.format_exc())
          pass
        pass
      else:
        pass

      self.task_step = self.task_step + 1

      self.current_time = datetime.datetime.now()
      self.elapsed_time = self.current_time - self.start_time
      self._update_total_time_estimate()
      self.ui.report_run_progress(self.task_step, self.tasks, self.total_time_estimate, self.elapsed_time)
      pass

    if self.state == RunState.Running:
      self.state = RunState.Success
      pass

    pass


  def _run_task(self, task, ui):
    task.setup()
    ui.report_task_progress(task.time_estimate, 0, 0, task)

    while task.progress < 100:
      task.poll()
      current_time = datetime.datetime.now()
      elapsed_time = current_time - task.start_time
      ui.report_task_progress(task.time_estimate,
                              elapsed_time,
                              task.progress,
                              task)
      # Update the estimate time with actual elapsed time.
      if task.progress >= 100:
        task.time_estimate = in_seconds(elapsed_time)
        pass

      if task.progress > 100:
        # something went wrong.
        self.state = RunState.Failed
        ui.report_task_failure(task.time_estimate,
                               elapsed_time,
                               task.progress,
                               task)
        task.teardown()
        break

      if task.progress == 100:
        # done
        ui.report_task_success(task.time_estimate,
                               elapsed_time,
                               task)
        task.teardown()
        pass
      pass
    pass

  def log(self, task, msg):
    self.ui.task_log(task, msg)
    pass

  pass
