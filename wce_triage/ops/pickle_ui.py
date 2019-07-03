#
# Pickle based UI. Didn't pan out too well as I have hoped.
# Will be kicked out from source tree.
#
import sys, os
from wce_triage.ops.ops_ui import *
import pickle

TASK_STATUS = ["waiting", "running", "done", "fail"]

#
# 
#
def _describe_task(task):
  if task.is_done:
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
          "message" : task.message }


class pickle_ui(ops_ui):
  def __init__(self):
    pass

  def send(self, event, obj):
    
    self.pickler.dump((event, obj))
    sys.stdout.flush()
    pass

  # Called from preflight to just set up the flight plan
  def report_tasks(self, runner_id, run_estimate, tasks):
    self.send("loadimage", { "device" : runner_id, 
                             "runEstimate" : round(in_seconds(run_estimate)),
                             "runTime": 0,
                             "steps" : [ _describe_task(task) for task in tasks ] } )
    pass

  #
  def report_task_progress(self, runner_id, run_estimate, run_time, time_estimate, elapsed_time, progress, task):
    self.send("loadimage", { "step": task.task_number,
                             "device": runner_id,
                             "runEstimate": run_estimate,
                             "runTime": round(in_seconds(run_time)),
                             "timeEstimate" : round(in_seconds(time_estimate)),
                             "message": task.message,
                             "progress" : progress,
                             "status": "running",
                             "elapseTime": round(in_seconds(elapsed_time)) })
    pass

  def report_task_failure(self,
                          runner_id,
                          task_estimate,
                          elapsed_time,
                          progress,
                          task):
    self.send("loadimage", { "step": task.task_number,
                             "device": runner_id,
                             "timeEstimate": round(in_seconds(task_estimate)),
                             "elapseTime": round(in_seconds(elapsed_time)),
                             "message": task.message,
                             "status": "fail",
                             "progress" : progress } )
    pass

  def report_task_success(self, runner_id, task_time_estimate, elapsed_time, task):
    self.send("loadimage", { "step": task.task_number,
                                "device": runner_id,
                                "message": task.message,
                                "progress" : 100,
                                "status": "done",
                                "elapseTime": round(in_seconds(elapsed_time)) } )
    pass

  def report_run_progress(self,
                          runner_id,
                          step,
                          tasks,
                          run_estimate,
                          run_time):
    self.send("loadimage", { "device" : runner_id,
                             "runEstimate" : round(in_seconds(run_estimate), 1),
                             "runTime": round(in_seconds(run_time), 1),
                             "steps" : [ _describe_task(task) for task in tasks ] } )
    pass

  # Log message. Probably better to be stored in file so we can see it
  # FIXME: probably should use python's logging.
  def log(self, runner_id, msg):
    self.send('message', {"message": runner_id + ": " + msg})
    pass

  pass


