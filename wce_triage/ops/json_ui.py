#
# 
#
import sys, os
from wce_triage.ops.ops_ui import *
import json
from wce_triage.ops.run_state import *

TASK_STATUS = ["waiting", "running", "done", "fail"]

#
# 
#
def _describe_task(task):
  if task.is_done and task.end_time:
    elapsed_time = round(in_seconds(task.end_time - task.start_time), 1)
  else:
    elapsed_time = round(in_seconds(datetime.datetime.now() - task.start_time) if task.start_time else 0, 1)
    pass
  return {"category" : task.get_description(),
          "status": TASK_STATUS[task._get_status()],
          "progress": task.progress,
          "timeEstimate": round(task.time_estimate, 1),
          "elapseTime": elapsed_time,
          "details": task.explain(),
          "step" : task.task_number if task.task_number else "",
          "message" : task.message,
          "explain" : task.explain(),
          "verdict": task.verdict }


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
  def report_tasks(self, runner_id, run_estimate, tasks):
    self.send(self.wock_event,
              { "device" : runner_id, 
                "runStatus" : "Prearing",
                "runEstimate" : round(in_seconds(run_estimate)),
                "runTime": 0,
                "steps" : [ _describe_task(task) for task in tasks ] } )
    pass

  #
  def report_task_progress(self, runner_id, run_estimate, run_time, time_estimate, elapsed_time, progress, task, tasks):
    self.send(self.wock_event,
              { "step": task.task_number,
                "device": runner_id,
                "runStatus": "Running step %d of %d tasks" % (task.task_number+1, len(tasks)),
                "runEstimate": round(run_estimate),
                "runTime": round(in_seconds(run_time)),
                "timeEstimate" : round(in_seconds(time_estimate)),
                "message": task.message,
                "progress" : round(progress, 1),
                "status": "running",
                "elapseTime": round(in_seconds(elapsed_time)) })
    pass

  def report_task_failure(self,
                          runner_id,
                          task_estimate,
                          elapsed_time,
                          progress,
                          task):
    if task.verdict:
      verdict = " ".join(task.verdict)
    else:
      verdict = task.message
      pass
    self.send(self.wock_event,
              { "step": task.task_number,
                "device": runner_id,
                "runStatus": verdict,
                "timeEstimate": round(in_seconds(task_estimate)),
                "elapseTime": round(in_seconds(elapsed_time)),
                "message": task.message,
                "status": "fail",
                "progress" : progress } )
    pass

  def report_task_success(self, runner_id, task_time_estimate, elapsed_time, task):
    if task.verdict:
      verdict = " ".join(task.verdict)
    else:
      verdict = task.message
      pass
    self.send(self.wock_event,
              { "step": task.task_number,
                "device": runner_id,
                "runStatus": verdict,
                "message": task.message,
                "progress" : 100,
                "status": "done",
                "elapseTime": round(in_seconds(elapsed_time)) } )
    pass

  def report_run_progress(self,
                          runner_id,
                          runner_state,
                          step,
                          tasks,
                          run_estimate,
                          run_time):

    status_message = runner_state

    if runner_state == "Success":
      status_message = self.message_catalog.get(runner_state, "Disk image operation completed successfully.")
    elif runner_state == "Failed":
      status_message = self.message_catalog.get(runner_state, "Disk image operation failed.")
    elif runner_state != "Running":
      status_message = self.message_catalog.get(runner_state, "Disk operation started.")
    elif step < len(tasks):
      this_task = tasks[step]
      description = this_task.description
      status_message_format = self.message_catalog.get(runner_state, "{step} of {steps}: Running {task}")
      status_message = status_message_format.format(task=description, step=step+1, steps=len(tasks))
      pass

    self.send(self.wock_event,
              { "device" : runner_id,
                "runStatus": status_message,
                "runEstimate" : round(in_seconds(run_estimate), 1),
                "runTime": round(in_seconds(run_time), 1),
                "steps" : [ _describe_task(task) for task in tasks ] } )
    pass

  # Log message. Probably better to be stored in file so we can see it
  # FIXME: probably should use python's logging.
  def log(self, runner_id, msg):
    print(msg)
    self.send('message', {"message": runner_id + ": " + msg})
    pass

  pass


