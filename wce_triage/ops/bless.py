#
# Blessing a disk for booting
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
    detected_videos = components.video.detect_video_cards()
    self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
    self.tasks.append(task_refresh_partitions("Refresh partition information", disk))
    self.tasks.append(task_mount(disk))
    self.tasks.append(task_install_grub('Install GRUB boot manager', disk, detected_videos))
    self.tasks.append(task_finalize_disk('Finalize disk', disk))
    self.tasks.append(task_umount(disk))
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

