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

import datetime, re, subproess

#
# Base class for disk operations
#
class DiskOp:
  def __init__(self, ui):
    self.ui = ui
    self.tasks = []
    pass

  @abstractmethod
  def prepare(self):
    pass

  @abstractmethod
  def prepare(self):
    pass

  def preflight(self):
    self.total_estimate_time = 0
    for task in tasks:
      self.total_estimate_time + task.estimate_time()
      pass
    self.ui.report_tasks(self.total_estimate_time, self.tasks)
    pass

  #
  def run(self):
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
      
      pass

    pass

  pass
