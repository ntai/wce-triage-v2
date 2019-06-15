
import abc

class ops_ui(object):
  def __init__(self):
    pass

  @abc.abstractmethod
  def report_tasks(self, msg):
    pass

  @abc.abstractmethod
  def print(self, msg):
    pass

  pass

class console_ui(object):
  def __init__(self):
    pass

  def report_tasks(self, total_estimate_time, tasks):
    print("Time estimate for %d tasks is %d" % (len(tasks), total_estimate_time))
    pass

  def print(self, msg):
    print(msg)
    pass

  pass


