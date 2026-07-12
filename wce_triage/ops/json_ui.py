#
# JSON UI
#
import sys
from .ops_ui import ops_ui
import json
from pydantic import BaseModel
from .run_state import RunState
from .protocol import OperationProgress, TaskStatus
from ..lib.util import get_triage_logger
from ..lib.timeutil import in_seconds

tlog = get_triage_logger()

TASK_STATUS = ["waiting", "running", "done", "fail"]

#
#
#
def _describe_task(task, current_time) -> TaskStatus:
  task_state = task._get_status()
  if task_state == 0:
    elapsed_time = 0
  elif task_state == 1:
    elapsed_time = round(in_seconds(current_time - task.start_time) if task.start_time else 0, 1)
  else:
    elapsed_time = round(in_seconds(task.end_time - task.start_time), 1)
    pass
  return TaskStatus(
    step=task.task_number if task.task_number is not None else 0,
    taskCategory=task.get_description(),
    taskProgress=task.progress,
    taskEstimate=round(task.time_estimate, 1),
    taskElapse=elapsed_time,
    taskStatus=TASK_STATUS[task_state],
    taskMessage=task.message,
    taskExplain=task.explain(),
    taskVerdict=task.verdict if task_state > 1 and task.verdict else [])


def _describe_tasks(tasks, current_time):
  """Flattens the runner's task list into TaskStatus entries. A task
  representing several parallel logical operations (describe_subtasks()
  returns non-None) expands into one entry per subtask."""
  result = []
  for task in tasks:
    subtasks = task.describe_subtasks(current_time)
    if subtasks is not None:
      result.extend(subtasks)
    else:
      result.append(_describe_task(task, current_time))
      pass
    pass
  return result


class json_ui(ops_ui):
  def __init__(self, wock_event = "loadimage", message_catalog=None):
    super().__init__()
    self.previous = None
    self.wock_event = wock_event
    self.message_catalog = message_catalog
    pass

  def send(self, event, obj):
    payload = obj.model_dump(mode="json", exclude_none=True) if isinstance(obj, BaseModel) else obj
    jata = json.dumps( { "event": event, "message": payload } )
    print(jata)
    sys.stdout.flush()
    pass

  # Called from preflight to just set up the flight plan
  def report_tasks(self, runner_id, current_time, run_estimate, tasks):
    self.send(self.wock_event, OperationProgress(
      report="tasks",
      device=runner_id,
      runStatus=RunState.Preflight,
      runMessage="Prearing",
      runEstimate=round(in_seconds(run_estimate)),
      runTime=0,
      tasks=_describe_tasks(tasks, current_time)))
    pass

  #
  def report_task_progress(self, runner_id, current_time, run_estimate, run_time, task, tasks):
    self.send(self.wock_event, OperationProgress(
      report="task_progress",
      device=runner_id,
      runStatus=RunState.Running,
      runMessage="Running step %d of %d tasks" % (task.task_number+1, len(tasks)),
      runEstimate=round(run_estimate),
      runTime=round(in_seconds(run_time)),
      step=task.task_number,
      tasks=_describe_tasks(tasks, current_time)))
    pass


  def report_task_failure(self, runner_id, current_time, run_time, task, tasks):
    self.send(self.wock_event, OperationProgress(
      report="task_failure",
      device=runner_id,
      runMessage="Task {step} failed".format(step=task.task_number+1),
      runStatus=RunState.Failed,
      runTime=round(in_seconds(run_time)),
      step=task.task_number,
      tasks=_describe_tasks(tasks, current_time)))
    pass

  def report_task_success(self, runner_id, current_time, run_time, task, tasks):
    self.send(self.wock_event, OperationProgress(
      report="task_success",
      device=runner_id,
      runMessage="Task {step} completed.".format(step=task.task_number+1),
      runStatus=RunState.Running,
      runTime=round(in_seconds(run_time)),
      step=task.task_number,
      tasks=_describe_tasks(tasks, current_time)))
    pass


  def report_run_progress(self, runner_id, current_time, runner_state, run_estimate, run_time, step, tasks):
    '''forms a json from run progress.
runner_id: is a device
current_time: datetime
runner_state: RunState enum
run_estimate: duration in seconds
run_time: run elapsed time so far.
step: index to tasks
tasks: array of tasks
'''
    status_message = runner_state.value

    if runner_state == RunState.Success:
      status_message = self.message_catalog.get(runner_state, "Disk image operation completed successfully.")
    elif runner_state == RunState.Failed:
      status_message = self.message_catalog.get(runner_state, "Disk image operation failed.")
    elif runner_state != RunState.Running:
      status_message = self.message_catalog.get(runner_state, "Disk operation started.")
    elif step < len(tasks):
      this_task = tasks[step]
      description = this_task.description
      status_message_format = self.message_catalog.get("runProgress", "{step} of {steps}: Running {desc}")
      status_message = status_message_format.format(desc=description, step=step+1, steps=len(tasks))
      pass
    elif step == len(tasks):
      raise Exception("You bonehead. Fix this first.")

    self.send(self.wock_event, OperationProgress(
      report="run_progress",
      device=runner_id,
      runStatus=runner_state,
      runMessage=status_message,
      runEstimate=round(in_seconds(run_estimate), 1),
      runTime=round(in_seconds(run_time), 1),
      tasks=_describe_tasks(tasks, current_time)))
    pass

  def log(self, runner_id, msg):
    tlog.info("JSON-LOG: " +  msg)
    self.send('message', {"message": runner_id + ": " + msg})
    pass

  pass

#
if __name__ == "__main__":
  print (TASK_STATUS)
  pass
