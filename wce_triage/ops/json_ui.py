#
# 
#
import sys, os
from wce_triage.ops.ops_ui import *
import json
from wce_triage.ops.run_state import *
from wce_triage.lib.util import *

tlog = get_triage_logger()

TASK_STATUS = ["waiting", "running", "done", "fail"]

#
# 
#
def _describe_task(task, current_time):
  result = {}
  task_state = task._get_status()
  if task_state == 0:
    elapsed_time = 0
  elif task_state == 1:
    elapsed_time = round(in_seconds(current_time - task.start_time) if task.start_time else 0, 1)
  else:
    elapsed_time = round(in_seconds(task.end_time - task.start_time), 1)
    pass
  result["step"] = task.task_number if task.task_number else ""
  result["taskCategory"] = task.get_description()
  result["taskProgress"] = task.progress
  result["taskEstimate"] = round(task.time_estimate, 1)
  result["taskElapse"] = elapsed_time
  result["taskStatus"] = TASK_STATUS[task._get_status()]
  result["taskMessage"] = task.message
  result["taskExplain"] = task.explain()

  if task._get_status() > 1:
    if task.verdict:
      result["taskVerdict"] = " ".join(task.verdict)
    else:
      result["taskVerdict"] = task.message
      pass
    pass

  return result


class json_ui(ops_ui):
  def __init__(self, wock_event = "loadimage", message_catalog=None):
    self.previous = None
    self.wock_event = wock_event
    self.message_catalog = message_catalog
    pass

  def send(self, event, obj):
    jata = json.dumps( { "event": event, "message": obj } )
    print(jata)
    sys.stdout.flush()
    pass

  # Called from preflight to just set up the flight plan
  def report_tasks(self, runner_id, current_time, run_estimate, tasks):
    describe_tasks = [ _describe_task(task, current_time) for task in tasks ]
    self.send(self.wock_event,
              { "report": "tasks",
                "device" : runner_id, 
                "runStatus" : RUN_STATE[RunState.Preflight.value],
                "runMessage" : "Prearing",
                "runEstimate" : round(in_seconds(run_estimate)),
                "runTime": 0,
                "tasks" : describe_tasks } )
    pass

  #
  def report_task_progress(self, runner_id, current_time, run_estimate, run_time, task, tasks):
    self.send(self.wock_event,
              {"report": "task_progress",
               "device": runner_id,
               "runStatus": RUN_STATE[RunState.Running.value],
               "runMessage": "Running step %d of %d tasks" % (task.task_number+1, len(tasks)),
               "runEstimate": round(run_estimate),
               "runTime": round(in_seconds(run_time)),
               "step": task.task_number,
               "task": _describe_task(task, current_time)})
    pass


  def report_task_failure(self, runner_id, current_time, run_time, task):
    self.send(self.wock_event, {
      "report": "task_failure",
      "device": runner_id,
      "runMessage": "Task {step} failed".format(step=task.task_number+1), 
      "runStatus": RUN_STATE[RunState.Failed.value],
      "runTime": round(in_seconds(run_time)),
      "step": task.task_number,
      "task": _describe_task(task, current_time)})
    pass

  def report_task_success(self, runner_id, current_time, run_time, task):
    self.send(self.wock_event, {
      "report": "task_success",
      "device": runner_id,
      "runMessage": "Task {step} completed.".format(step=task.task_number+1), 
      "runStatus": RUN_STATE[RunState.Running.value],
      "runTime": round(in_seconds(run_time)),
      "step": task.task_number,
      "task": _describe_task(task, current_time)})
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
    status_message = RUN_STATE[runner_state.value]

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

    self.send(self.wock_event,
              { "report": "run_progress",
                "device" : runner_id,
                "runStatus": RUN_STATE[runner_state.value],
                "runMessage": status_message,
                "runEstimate" : round(in_seconds(run_estimate), 1),
                "runTime": round(in_seconds(run_time), 1),
                "tasks" : [ _describe_task(task, current_time) for task in tasks ] } )
    pass

  # Log message. Probably better to be stored in file so we can see it
  # FIXME: probably should use python's logging.
  def log(self, runner_id, msg):
    tlog.info(msg)
    self.send('message', {"message": runner_id + ": " + msg})
    pass

  pass

#
if __name__ == "__main__":
  print (TASK_STATUS)
  pass

