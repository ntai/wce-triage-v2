#
# Blessing a disk for booting
#
# The runner initializes disk, loads up the GRUB boot loader
#

import datetime, re, subprocess, sys, os

from wce_triage.ops.tasks import *
from wce_triage.ops.ops_ui import *
from wce_triage.ops.runner import *
from wce_triage.components.disk import Disk, Partition

#
#
class BlessDisk(Runner):
  def __init__(self, ui, disk, partition_id='Linux'):
    super().__init__(ui)
    self.disk = disk
    # FIXME: may become a task
    self.disk.detect_disk()
    self.time_estimate = 2
    pass

  def prepare(self):
    super().prepare()
    self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
    self.tasks.append(task_refresh_partitions("Refresh partition information", disk))
    self.tasks.append(task_mount("Mount disk %s" % disk.device_name, disk, partition_id=partition_id))
    mock_video = (0, 0, 1)
    self.tasks.append(task_install_grub('Install GRUB boot manager', disk, mock_video, partition_id=partition_id))
    self.tasks.append(task_finalize_disk('Finalize disk', disk, partition_id=partition_id))
    unmounter = task_unmount("Unmount disk %s" % disk.device_name, disk, partition_id=partition_id)
    unmounter.set_teardown_task()
    self.tasks.append(unmounter)
    pass

  pass


if __name__ == "__main__":
  devname = sys.argv[1]
  partition_id = 'Linux'
  if len(sys.argv) > 2:
    partition_id = sys.argv[2]
    pass
  disk = Disk(device_name=devname)
  ui = console_ui()
  runner = BlessDisk(ui, disk, partition_id=partition_id)
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass
