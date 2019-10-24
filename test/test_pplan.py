import unittest
from wce_triage.components.disk import *
from wce_triage.ops.pplan import *

disk = Disk(device_name="/dev/null")
disk.byte_size = 64 * 2**30

class Test_(unittest.TestCase):

  def test_partition_plan_0(self):
    for efi_boot in [ False, True ]:
      for ext4_version in [ None, "1.42"]:
        plan = make_usb_stick_partition_plan(disk, ext4_version=ext4_version, efi_boot=efi_boot)

        for part in plan:
          print( "EFI = {} Version = {} Part {} {} {} {}".format(str(efi_boot), ext4_version, part.no, part.start, part.size, part.parttype))
          pass

        self.assertEqual(len(plan), 3 if efi_boot else 2)
        pass
      pass
    pass


if __name__ == '__main__':
  unittest.main()
