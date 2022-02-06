import typing
import sys

class View(object):
  def updating(self, t0: dict, update: typing.Optional[any]):
    # if t0:
    #   point_a = set(t0.items())
    #   point_b = set(t1.items())
    #   removed = point_a - point_b
    #   added = point_b - point_a
    #   pass
    # else:
    #   pass
    pass

  def updated(self, t1: dict):
    pass


class ConsoleView(View):
  def updating(self, t0: dict, update: typing.Optional[any]):
    if update.get("severity", 0) > 1:
      sys.stderr.write("#2: " + update.get("message", ""))
      sys.stderr.flush()
    else:
      sys.stdout.write("#1: " + update.get("message", ""))
      sys.stdout.flush()
      pass
    pass

class SocketView(view):

  def updated(self, t1: dict):

