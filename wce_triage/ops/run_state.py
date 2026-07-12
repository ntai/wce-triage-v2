from enum import Enum

class RunState(str, Enum):
  """Run state of a runner/task. Values double as the wire representation
  used in NDJSON progress reports (the `runStatus` field)."""
  Initial = "Waiting"
  Prepare = "Prepare"
  Preflight = "Preflight"
  Running = "Running"
  Success = "Success"
  Failed = "Failed"
  pass

# Kept for backward compatibility with any external code indexing by ordinal.
RUN_STATE = [RunState.Initial.value, RunState.Prepare.value, RunState.Preflight.value,
             RunState.Running.value, RunState.Success.value, RunState.Failed.value]
