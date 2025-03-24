#
"""tasks to configure machine
"""

import re, os

from ..ops.tasks import op_task_python_simple, fstab_template, efi_template, swap_template
from ..lib import get_triage_logger
from ..lib.grub import grub_set_wce_share
from ..ops.pplan import EFI_NAME

tlog = get_triage_logger()

#
# Generating pxeboot
#
class task_config_pxeboot(op_task_python_simple):
  """Read the pxeboot config file and generate it"""
  def __init__(self, description, **kwargs):
    super().__init__(description, time_estimate=1, **kwargs)
    pass
   

  def run_python(self):
    #
    self.linuxpart = self.disk.find_partition(self.partition_id)
    if self.linuxpart is None:
      msg = "Partition with %s does not exist." % str(self.partition_id)
      self.set_progress(999, msg)

      tlog.debug("part n = %d" % len(self.disk.partitions))
      for part in self.disk.partitions:
        tlog.debug( str(part))
        pass
      raise Exception(msg)

    self.efi_part = self.disk.find_partition(EFI_NAME)
    self.swappart = self.disk.find_partition_by_file_system("swap")
    self.mount_dir = self.linuxpart.get_mount_point()

    # patch up the restore
    fstab = open("%s/etc/fstab" % self.mount_dir, "w")
    fstab.write(fstab_template % (self.linuxpart.fs_uuid))
    if self.efi_part:
      fstab.write(efi_template % self.efi_part.fs_uuid)
      pass
    if self.swappart:
      fstab.write(swap_template % (self.swappart.fs_uuid))
      pass
    fstab.close()

    #
    # New hostname
    #
    if self.newhostname:
      # Set up the /etc/hostname
      etc_hostname_filename = "%s/etc/hostname" % self.mount_dir
      hostname_file = open(etc_hostname_filename, "w")
      hostname_file.write("%s\n" % self.newhostname)
      hostname_file.close()

      # Set up the /etc/hosts file
      etc_hosts_filename = "%s/etc/hosts" % self.mount_dir
      hosts = open(etc_hosts_filename, "r")
      lines = hosts.readlines()
      hosts.close()
      hosts = open(etc_hosts_filename, "w")

      this_host = re.compile(r"127\.0\.1\.1\s+[a-z_A-Z0-9]+\n")
      for line in lines:
        m = this_host.match(line)
        if m:
          hosts.write("127.0.1.1\t%s\n" % self.newhostname)
        else:
          hosts.write(line)
          pass
        pass
      hosts.close()

      self.log("Hostname in %s/etc is updated with %s." % (self.mount_dir, self.newhostname))
      pass

    # Set the wce_share_url to /etc/default/grub
    if self.wce_share_url is not None:
      grub_file = "%s/etc/default/grub" % self.mount_dir
      updated, contents = grub_set_wce_share(filename=grub_file, wce_share=self.wce_share_url)
      if updated:
        grub = open(grub_file, "w")
        grub.write(contents)
        grub.close()
        pass
      pass

    #
    # Remove the WCE follow up files
    # 
    for removing in ["%s/var/lib/world-computer-exchange/computer-uuid",
                     "%s/var/lib/world-computer-exchange/access-timestamp"]:
      try:
        os.unlink( removing % self.mount_dir)
      except:
        # No big deal if the file isn't there or failed to remove.
        pass
      pass
    pass
  pass

