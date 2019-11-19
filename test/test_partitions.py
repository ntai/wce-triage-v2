import unittest
from wce_triage.ops import pplan as _pplan
from wce_triage.components import disk as _disk
from wce_triage.const import *


class Test_partitions(unittest.TestCase):

  def test_make_efi_partition_plan(self):
    disk = _disk.Disk("/dev/null")
    disk._set_byte_size(40 * (2 ** 30))
    pplan = _pplan.make_efi_partition_plan(disk, ext4_version=None, efi_boot=False, partition_id=None)
    #print("EFI")
    #_pplan.print_pplan(pplan)
    self.assertEqual(len(pplan), 5)
    part1 = pplan[1]
    self.assertEqual(part1.start, 2)
    part2 = pplan[2]
    self.assertEqual(part2.start, 34)
    self.assertEqual(part2.partcode, 'EF00')
    part3 = pplan[3]
    self.assertEqual(part3.start, 546)
    self.assertEqual(part3.partcode, '8200')
    part4 = pplan[4]
    self.assertEqual(part4.start, 2594)
    self.assertEqual(part4.partcode, '8300')

    pplan = _pplan.make_efi_partition_plan(disk, ext4_version=const.ext4_version_no_metadata_csum, efi_boot=False, partition_id=None)
    #print("EFI no metadata csum")
    #_pplan.print_pplan(pplan)
    part4 = pplan[4]
    self.assertEqual(part4.mkfs_opts, ['-O', '^metadata_csum'])
    pass


  def test_make_traditional_partition_plan(self):
    disk = _disk.Disk("/dev/null")
    disk._set_byte_size(60 * (2 ** 30))
    pplan = _pplan.make_traditional_partition_plan(disk, ext4_version=None, partition_id=None)
    #print("Traditional")
    #_pplan.print_pplan(pplan)

    self.assertEqual(len(pplan), 3)
    part1 = pplan[1]
    self.assertEqual(part1.start, 2)
    self.assertEqual(part1.partcode, '8300')
    self.assertEqual(part1.flags, 'boot')

    pplan = _pplan.make_traditional_partition_plan(disk, ext4_version=const.ext4_version_no_metadata_csum, partition_id=None)
    #print("Traditional no metadata csum")
    #_pplan.print_pplan(pplan)
    self.assertEqual(len(pplan), 3)
    part1 = pplan[1]
    self.assertEqual(part1.start, 2)
    self.assertEqual(part1.partcode, '8300')
    self.assertEqual(part1.flags, 'boot')
    self.assertEqual(part1.mkfs_opts, ['-O', '^metadata_csum'])

    part2 = pplan[2]
    self.assertEqual(part2.start, 58367)
    self.assertEqual(part2.partcode, '8200')
    pass

  def test_make_usb_stick_partition_plan(self):
    disk = _disk.Disk("/dev/null")
    disk._set_byte_size(40 * (2 ** 30))
    pplan = _pplan.make_usb_stick_partition_plan(disk, partition_id=None, ext4_version=None, efi_boot=False)
    #print("USB")
    #_pplan.print_pplan(pplan)
    self.assertEqual(len(pplan), 2)
    pass


  def test_partition_lister(self):
    disk = _disk.Disk("/dev/null")
    disk._set_byte_size(40 * (2 ** 30))
    lister = _disk.PartitionLister(disk)
    out = """BYT;
/dev/sdc:117210240s:scsi:512:512:msdos:TOSHIBA MK6034GSX:;
1:4096s:111347711s:111343616s:ext4::boot;
2:111347712s:117207039s:5859328s:linux-swap(v1)::;
"""
    err = ""
    lister.set_parted_output(out, err)
    lister.parse_parted_output()
    self.assertEqual(len(disk.partitions), 2)
    pass
  pass

if __name__ == '__main__':
  unittest.main()
