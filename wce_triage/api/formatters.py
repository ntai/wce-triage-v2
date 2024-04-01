
def jsoned_disk(disk):
  return {"target": 0,
          "deviceName": disk.device_name,
          "runTime": 0,
          "runEstimate": 0,
          "mounted": disk.mounted,
          "size": round(disk.get_byte_size() / 1000000), # in MB (not MiB)
          "bus": "usb" if disk.is_usb else "ata",
          "model": disk.model_name,
          "vendor": disk.vendor,
          "serial_no": disk.serial_no,
          "smart": disk.smart,
          "smart_enabled": disk.smart_enabled,
  }

def jsoned_optical(optical):
  return {"deviceName": optical.device_name,
          "model": optical.vendor + " " + optical.model_name }

#
# This is ugly as hell. json_ui needs a better design.
#
def update_runner_status(runner_status, progress):
  # load image event has two types, one from report_task_progress and other from report_tasks
  # report_tasks contains the tasks, and task progress only updates the small part.

  # If it includes all of tasks, use it.
  if progress.get("tasks"):
    runner_status = {"tasks": progress["tasks"]}
    pass

  # If it includes the task and it's step number,
  # update the task.
  # FIXME: Probalby it's better to replace the task
  if progress.get("task") and progress.get("step"):
    step = progress["step"]
    task = progress["task"]
    tasks = runner_status.get("tasks")
    if tasks and step < len(tasks):
      runner_status["tasks"][step]["taskProgress"] = task["taskProgress"]
      runner_status["tasks"][step]["taskElapse"] = task["taskElapse"]
      if task["taskMessage"]:
        runner_status["tasks"][step]["taskMessage"] = task["taskMessage"]
        pass
      runner_status["tasks"][step]["taskStatus"] = task["taskStatus"]
      pass
    pass
  return runner_status
