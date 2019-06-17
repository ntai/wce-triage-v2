from enum import Enum

class RunState(Enum):
  Initial = 0
  Prepare = 1
  Preflight = 2
  Running = 3
  Success = 4
  Failed = 5
  pass
