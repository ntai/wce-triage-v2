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
from wce_triage.ops.run_state import RunState
from wce_triage.lib.timeutil import *

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
    '''prepare is for runner's preparation, not for tasks. during prepare,
       runner should create tasks.'''
    if self.state != RunState.Initial:
      raise Exception("Run state is not initial")
    self.state = RunState.Prepare
    self.task_step = 0
    pass


  def preflight(self):
    '''preflight is for tasks's preparation, not for runner. during prepare,
       tasks should initalize all the necessary actions.
       however, task has one more shot at set up which is run just before
       polling starts.'''

    if self.state != RunState.Prepare:
      raise Exception("Run state is not Prepare")

    self.state = RunState.Preflight

    # Tell the tasks I'm the runner.
    task_number = 0
    for task in self.tasks:
      task.task_number = task_number
      task.runner = self
      task_number += 1
      pass

    # This gives a chance for tasks to know the neighbors.
    for task in self.tasks:
      task.preflight(self.tasks)
      pass

    self._update_total_time_estimate()
    self.ui.report_tasks(self.total_time_estimate, self.tasks)
    pass

  def _update_total_time_estimate(self):
    self.total_time_estimate = 0
    for task in self.tasks:
      task_time_estimate = task.estimate_time()
      if task_time_estimate is None:
        raise Exception( task.description + " has no time estimate")
      self.total_time_estimate += task_time_estimate
      pass
    pass
  
  # Explaining what's going to happen
  def explain(self):
    self.ui.report_tasks(self.total_time_estimate, self.tasks)
    pass

  def report_current_task(self):
    self.current_time = datetime.datetime.now()
    self.elapsed_time = self.current_time - self.start_time
    self._update_total_time_estimate()
    self.ui.report_run_progress(self.task_step, self.tasks, self.total_time_estimate, self.elapsed_time)
    pass

  #
  def run(self):
    if self.state != RunState.Preflight:
      raise Exception("Run state is not Preflight")
    self.state = RunState.Running

    self.start_time = datetime.datetime.now()
    self.report_current_task()
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
      self.report_current_task()
      pass

    if self.state == RunState.Running:
      self.state = RunState.Success
      pass

    pass


  def _run_task(self, task, ui):
    task.setup()
    current_time = datetime.datetime.now()
    ui.report_task_progress(current_time - self.start_time, task.time_estimate, 0, 0, task)

    while task.progress < 100:
      task.poll()
      current_time = datetime.datetime.now()
      task_elapsed_time = current_time - task.start_time
      ui.report_task_progress(current_time - self.start_time,
                              task.time_estimate,
                              task_elapsed_time,
                              task.progress,
                              task)
      # Update the estimate time with actual elapsed time.
      if task.progress >= 100:
        task.time_estimate = in_seconds(task_elapsed_time)
        pass

      if task.progress > 100:
        # something went wrong.
        self.state = RunState.Failed
        ui.report_task_failure(task.time_estimate,
                               task_elapsed_time,
                               task.progress,
                               task)
        task.teardown()
        break

      if task.progress == 100:
        # done
        ui.report_task_success(task.time_estimate, task_elapsed_time, task)
        task.teardown()
        pass
      pass
    pass

  def log(self, task, msg):
    self.ui.task_log(task, msg)
    pass

  pass
