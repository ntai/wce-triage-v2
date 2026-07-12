#!/usr/bin/env python3
#
# Wipe disks - standalone, outside of a load/restore operation.
#
# Wipes one or more disks in parallel (same bin/multiwipe.py process used by
# op_task_wipe_disk for a single disk), reported through the same Runner +
# json_ui machinery as save/load/sync so all four operations share one wire
# shape (protocol.OperationProgress).
#

import sys, argparse, traceback

from .runner import Runner
from .ops_ui import console_ui
from .json_ui import json_ui
from .tasks import task_multiwipe
from ..lib.util import is_block_device, get_triage_logger
from ..components.disk import create_storage_instance

tlog = get_triage_logger()

# "Waiting", "Prepare", "Preflight", "Running", "Success", "Failed"
my_messages = { "Waiting":   "Disk wipe is waiting.",
                "Prepare":   "Disk wipe is preparing.",
                "Preflight": "Disk wipe is preparing.",
                "Running":   "{step} of {steps}: Running {task}",
                "Success":   "Disk wipe completed successfully.",
                "Failed":    "Disk wipe failed." }


class WipeRunner(Runner):
  """Runner that wipes one or more disks in parallel via bin/multiwipe.py."""

  def __init__(self, ui, runner_id, devices, short=False):
    super().__init__(ui, runner_id)
    self.devices = devices
    self.short = short
    pass

  def prepare(self):
    super().prepare()
    desc = ("Wipe first 1Mb of %d disk(s)" if self.short else "Wipe %d disk(s)") % len(self.devices)
    disks = [create_storage_instance(device) for device in self.devices]
    self.tasks.append(task_multiwipe(desc, devices=self.devices, short=self.short, disks=disks))
    pass

  pass


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Wipe disks using bin/multiwipe.py.")
  parser.add_argument("devices", help="Comma-separated device names to wipe.")
  parser.add_argument("-s", "--short", action="store_true", help="Wipe only the first 1MB of each disk.")
  parser.add_argument("-c", "--cli", action="store_true", help="Console UI instead of JSON UI, for testing.")
  args = parser.parse_args()

  devices = [device.strip() for device in args.devices.split(",") if device.strip()]
  for device in devices:
    if not is_block_device(device):
      sys.stderr.write("%s is not a block device.\n" % device)
      sys.exit(1)
      pass
    pass

  ui = console_ui() if args.cli else json_ui(wock_event="zerowipe", message_catalog=my_messages)

  runner = WipeRunner(ui, ",".join(devices), devices, short=args.short)
  try:
    runner.prepare()
    runner.preflight()
    runner.explain()
    runner.run()
    sys.exit(0)
    # NOTREACHED
  except Exception as _exc:
    sys.stderr.write(traceback.format_exc() + "\n")
    sys.exit(1)
    # NOTREACHED
    pass
  pass
