#
# Blessing a disk for booting
#
# The runner initializes disk, loads up the GRUB boot loader
#

import sys
from .runner import Runner
from .ops_ui import console_ui
from .tasks import task_fetch_partitions, task_refresh_partitions, task_mount, task_install_grub, task_finalize_disk, task_unmount
from ..components.disk import create_storage_instance

#
class BlessDiskRunner(Runner):
  def __init__(self, ui, runner_id, disk, partition_id='Linux'):
    super().__init__(ui, runner_id)
    self.disk = disk
    # FIXME: may become a task
    self.disk.detect_disk()
    self.time_estimate = 2
    self.partition_id = partition_id
    pass

  def prepare(self):
    super().prepare()
    self.tasks.append(task_fetch_partitions("Fetch disk information", disk))
    self.tasks.append(task_refresh_partitions("Refresh partition information", disk))
    self.tasks.append(task_mount("Mount disk %s" % disk.device_name, disk, partition_id=self.partition_id))
    mock_video = (0, 0, 1)
    self.tasks.append(task_install_grub('Install GRUB boot manager', disk=disk, detected_videos=mock_video, partition_id=self.partition_id))
    self.tasks.append(task_finalize_disk('Finalize disk', disk, partition_id=self.partition_id))
    unmounter = task_unmount("Unmount disk %s" % disk.device_name, disk, partition_id=self.partition_id)
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
  disk = create_storage_instance(devname)
  ui = console_ui()
  runner = BlessDiskRunner(ui, disk.device_name, disk, partition_id=partition_id)
  runner.prepare()
  runner.preflight()
  runner.explain()
  runner.run()
  pass
