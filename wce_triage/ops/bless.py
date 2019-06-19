#
# Blessing a disk for booting
#
# The runner initializes disk, loads up the GRUB boot loader
#

import datetime, re, subprocess, sys, os

if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

from ops.tasks import *
from ops.ops_ui import *
from components.disk import Disk, Partition
from runner import *

#
#
class BlessDisk(Runner):
  def __init__(self, ui, disk):
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
    self.tasks.append(task_mount("Mount disk %s" % disk.device_name, disk))
    self.tasks.append(task_install_grub('Install GRUB boot manager', disk, (0, 0, 1)))
    self.tasks.append(task_finalize_disk('Finalize disk', disk))
    self.tasks.append(task_unmount("Unmount disk %s" % disk.device_name, disk))
    pass

  pass


if __name__ == "__main__":
  devname = sys.argv[1]
  disk = Disk(device_name=devname)
  ui = console_ui()
  runner = BlessDisk(ui, disk)
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass
