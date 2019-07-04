#
# Operation UI
#
# FIXME: The signature change is painful
# It probably means keyword based arguments is easier.
# However, that makes it error prone.
# I think making the argument as namedtuple may solve the
# strictness and flexibility.
#
import abc
import datetime
from wce_triage.lib.timeutil import *
from wce_triage.ops.run_state import RunState

class ops_ui(object):
  def __init__(self):
    pass

  
  @abc.abstractmethod
  def report_tasks(self, runner_id, run_estimate, tasks):
    '''report_tasks is called at preflight to report the total
       estimate time for all of tasks.
       runner_id: unique runner ID - often device name
    '''
    pass

  @abc.abstractmethod
  def report_task_progress(self, runner_id, run_estimate, run_time, task_estimate, task_elapsed_time, progress, task, tasks):
    '''report_task_progress is called at semi-regular interval to 
       report the current progress. 
       progress: 0-100
    '''
    pass

  @abc.abstractmethod
  def report_task_failure(self,
                          runner_id, 
                          task_estimate,
                          elapsed_time,
                          progress,
                          task):
    pass

  @abc.abstractmethod
  def report_task_success(self, 
                          runner_id,
                          task_time_estimate,
                          elapsed_time,
                          task):
    pass

  @abc.abstractmethod
  def report_run_progress(self,
                          runner_id, 
                          runner_state,
                          step,
                          tasks,
                          run_estimate,
                          run_time):
    pass


  # message be printed and shown somewhere.
  @abc.abstractmethod
  def log(self, runner_id, msg):
    pass

  def task_log(self, runner_id, task, msg):
    self.log(runner_id, "%s: (%s) %s" % (runner_id, task.description, msg))
    pass
  pass


class console_ui(ops_ui):
  def __init__(self):
    self.last_report_time = datetime.datetime.now()
    pass

  # Used for explain. Probably needs better way
  def report_tasks(self, runner_id, run_estimate, tasks):
    index = 0
    for task in tasks:
      index = index + 1
      print( "%s %d: %s %s" % (runner_id, index, task.description, task.explain()))
      pass
    print("Time estimate for %d tasks is %d" % (len(tasks), in_seconds(run_estimate)))
    pass

  #
  def report_task_progress(self, runner_id, run_estimate, run_time, time_estimate, elapsed_time, progress, task, tasks):
    current_time = datetime.datetime.now()
    dt = in_seconds( current_time - self.last_report_time )
    if dt < 0:
      return
    
    msg = (" " + task.message) if task and task.message else ""
    self.last_report_time = current_time
    print("%s %3d: %d%% done. Estimate for %s is %d.%s" % (runner_id, in_seconds(run_time), in_seconds(progress), task.description, time_estimate, msg))
    pass


  def report_task_failure(self,
                          runner_id,
                          task_estimate,
                          elapsed_time,
                          progress,
                          task):
    print("%s %s failed in %d seconds. Aborting." % (runner_id, task.description, in_seconds(elapsed_time)))
    print(task.message)
    pass

  def report_task_success(self, runner_id, task_time_estimate, elapsed_time, task):
    print("%s %s finised in %d seconds." % (runner_id, task.description, in_seconds(elapsed_time)))
    pass

  def report_run_progress(self, 
                          runner_id,
                          runner_state,
                          step,
                          tasks,
                          run_estimate,
                          run_time):
    print("%s %s %3d: (%d/%d) estimate %d seconds." % (runner_id, runner_state,
                                                       in_seconds(run_time),
                                                       step, len(tasks),
                                                       in_seconds(run_estimate)))
    pass


  # Log message. Probably better to be stored in file so we can see it
  # FIXME: probably should use python's logging.
  def log(self, runner_id, msg):
    print(runner_id + ": " + msg)
    pass

  pass


class virtual_ui(ops_ui):
  def __init__(self):
    self.state = RunState.Initial
    pass

  #
  def report_tasks(self, runner_id, run_estimate, tasks):
    pass

  #
  def report_task_progress(self, runner_id, run_estimate, run_time, time_estimate, elapsed_time, progress, task, tasks):
    pass

  def report_task_failure(self,
                          runner_id,
                          task_estimate,
                          elapsed_time,
                          progress,
                          task):
    self.state = RunState.Failed
    pass

  def report_task_success(self, 
                          runner_id,
                          task_time_estimate,
                          elapsed_time,
                          task):
    self.state = RunState.Success
    pass

  def report_run_progress(self, 
                          runner_id,
                          runner_state,
                          step,
                          tasks,
                          run_estimate,
                          run_time):
    pass

  # Used for explain.
  def log(self, runner_id, msg):
    pass

  pass


