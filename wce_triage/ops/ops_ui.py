
import abc
import datetime
from lib.timeutil import *
from ops.run_state import RunState

class ops_ui(object):
  def __init__(self):
    pass

  
  @abc.abstractmethod
  def report_tasks(self, total_estimate_time, tasks):
    '''report_tasks is called at preflight to report the total
       estimate time for all of tasks.
    '''
    pass

  @abc.abstractmethod
  def report_task_progress(self, estimate_time, elapsed_time, progress, task):
    '''report_task_progress is called at semi-regular interval to 
       report the current progress. 
       progress: 0-100
    '''
    pass

  @abc.abstractmethod
  def report_task_failure(self,
                          task_estimate_time,
                          elapsed_time,
                          progress,
                          task):
    pass

  @abc.abstractmethod
  def report_task_success(self, 
                          task_estimate_time,
                          elapsed_time,
                          progress,
                          task):
    pass

  @abc.abstractmethod
  def report_run_progress(self,
                          step,
                          tasks,
                          task_estimate_time,
                          elapsed_time):
    pass


  @abc.abstractmethod
  def print(self, msg):
    pass

  pass

class console_ui(object):
  def __init__(self):
    self.last_report_time = datetime.datetime.now()
    pass

  #
  def report_tasks(self, total_estimate_time, tasks):
    print("Time estimate for %d tasks is %d" % (len(tasks), in_seconds(total_estimate_time)))
    pass

  #
  def report_task_progress(self, estimate_time, elapsed_time, progress, task):
    current_time = datetime.datetime.now()
    dt =in_seconds( current_time - self.last_report_time )
    if dt < 0:
      return
    self.last_report_time = current_time
    print("%d%% done. Time estimate for %s is %d" % (in_seconds(progress), task.description, task.estimate_time()))
    pass


  def report_task_failure(self,
                          task_estimate_time,
                          elapsed_time,
                          progress,
                          task):
    print("%s failed in %d seconds. Aborting." % (task.description, in_seconds(elapsed_time)))
    print(task.message)
    pass

  def report_task_success(self, 
                          task_estimate_time,
                          elapsed_time,
                          progress,
                          task):
    print("%s finised in %d seconds." % (task.description, in_seconds(elapsed_time)))
    pass

  def report_run_progress(self, 
                          step,
                          tasks,
                          total_estimate_time,
                          elapsed_time):
    print("(%d/%d) elapsed %d, estimate %d seconds." % (step, len(tasks),
                                                        in_seconds(elapsed_time),
                                                        in_seconds(total_estimate_time)))
    pass

  # Used for explain. Probably needs better way
  def print(self, msg):
    print(msg)
    pass

  pass


class virtual_ui(object):
  def __init__(self):
    self.state = RunState.Initial
    pass

  #
  def report_tasks(self, total_estimate_time, tasks):
    pass

  #
  def report_task_progress(self, estimate_time, elapsed_time, progress, task):
    pass

  def report_task_failure(self,
                          task_estimate_time,
                          elapsed_time,
                          progress,
                          task):
    self.state = RunState.Failed
    pass

  def report_task_success(self, 
                          task_estimate_time,
                          elapsed_time,
                          progress,
                          task):
    self.state = RunState.Success
    pass

  def report_run_progress(self, 
                          step,
                          tasks,
                          total_estimate_time,
                          elapsed_time):
    pass

  # Used for explain.
  def print(self, msg):
    pass

  pass


