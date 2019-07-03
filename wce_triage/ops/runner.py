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
import functools

#
# Base class for runner
#
class Runner:
  
  def __init__(self, ui, runner_id):
    self.state = RunState.Initial
    self.ui = ui
    self.runner_id = runner_id
    self.tasks = []
    self.run_estimate = 0
    self.run_time = 0
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

    self._update_run_estimate()
    self.ui.report_tasks(self.runner_id, self.run_estimate, self.tasks)
    pass

  def _update_run_estimate(self):
    self.run_estimate = 0
    for task in self.tasks:
      task_time_estimate = task.estimate_time()
      if task_time_estimate is None:
        raise Exception( task.description + " has no time estimate")
      self.run_estimate += task_time_estimate
      pass
    pass
  
  # Explaining what's going to happen
  def explain(self):
    self.ui.report_tasks(self.runner_id, self.run_estimate, self.tasks)
    pass

  def report_current_task(self):
    self.current_time = datetime.datetime.now()
    self.run_time = self.current_time - self.start_time
    self._update_run_estimate()
    self.ui.report_run_progress(self.runner_id, self.task_step, self.tasks, self.run_estimate, self.run_time)
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
          self.ui.log(self.runner_id, "Task: " + task.description + "\n" + traceback.format_exc())
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
    run_time = current_time - self.start_time
    last_progress_time = current_time

    ui.report_task_progress(self.runner_id, self.run_estimate, run_time, task.time_estimate, 0, 0, task)

    while task.progress < 100:
      task.poll()
      current_time = datetime.datetime.now()
      task_elapsed_time = current_time - task.start_time

      if in_seconds(current_time - last_progress_time) >= 0.75:
        last_progress_time = current_time
        self._update_run_estimate()

        # When the poll comes back too fast, this creates a lot of traffic.
        # Need to tame down a little
        ui.report_task_progress(self.runner_id,
                                self.run_estimate,
                                current_time - self.start_time,
                                task.time_estimate,
                                task_elapsed_time,
                                task.progress,
                                task)
        pass

      # Update the estimate time with actual elapsed time.
      if task.progress >= 100:
        task.time_estimate = in_seconds(task_elapsed_time)
        pass

      if task.progress > 100:
        # something went wrong.
        self.state = RunState.Failed
        task.teardown()
        ui.report_task_failure(self.runner_id,
                               task.time_estimate,
                               task_elapsed_time,
                               task.progress,
                               task)
        break

      if task.progress == 100:
        # done
        task.teardown()
        ui.report_task_success(self.runner_id, task.time_estimate, task_elapsed_time, task)
        pass
      pass
    pass

  def log(self, task, msg):
    self.ui.task_log(self.runner_id, task, msg)
    pass

  pass
