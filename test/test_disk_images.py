import unittest
from wce_triage.components.disk import *
from wce_triage.lib.disk_images import *
import subprocess
import tempfile
import shutil
import os
ROOTDIR=os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")

tlog = init_triage_logger(filename='/tmp/disk_images.log')

disk = Disk(device_name="/dev/null")
disk.byte_size = 64 * 2**30

class Test_DiskImages(unittest.TestCase):

  def setUp(self):
    self.test_dir = tempfile.mkdtemp()
    cmd = ["rsync", "-a", os.path.join(ROOTDIR, "wce_triage/setup/share/wce/wce-disk-images"), self.test_dir]
    subprocess.run(cmd)
    set_wce_disk_image_dir(os.path.join(self.test_dir, "wce-disk-images"))

    test1 = os.path.join(self.test_dir, "wce-disk-images", "wce-18", "test1.partclone.gz")
    test2 = os.path.join(self.test_dir, "wce-disk-images", "wce-16", "test2.partclone.gz")
    
    for testfile in [ test1, test2 ]:
      with open(testfile, "w") as test_fd:
        test_fd.write("FOO!")
        test_fd.close()
        pass
      pass

    self.image_types = [
      {'id': 'network-server', 'filestem': 'network-server', 'name': 'WCE Network Server', 'timestamp': True, 'efi_image': '.efi-512M.fat32.partclone.gz', 'hostname': 'wcebos1', 'randomize_hostname': False, 'partition_map': 'gpt', 'cmdline': {'nvme_core.default_ps_max_latency_us': '5500', 'splash': '_REMOVE_', 'quiet': '_REMOVE_'}},
      {'id': 'triage-x32', 'filestem': 'triage-x32', 'name': 'Triage x86 32bit USB flash drive', 'timestamp': True, 'partition_plan': 'triage', 'partition_map': 'msdos', 'media': 'usb-flash', 'wce_share_url': '/usr/local/share/wce', 'cmdline': {'forcepae': None, 'acpi_enforce_resources': 'lax', 'quiet': '_REMOVE_', 'splash': '_REMOVE_'}},
      {'id': 'wce-18', 'filestem': 'wce-mate18', 'name': 'WCE Ubuntu 18.04LTS', 'timestamp': True, 'efi_image': '.efi-512M.fat32.partclone.gz', 'partition_map': 'gpt', 'hostname': 'wce', 'randomize_hostname': True, 'cmdline': {'acpi_enforce_resources': 'lax', 'nvme_core.default_ps_max_latency_us': '5500'}},
      {'id': 'wce-lubuntu-18-x32', 'filestem': 'wce-lubuntu-18-x32', 'name': 'WCE Lubuntu 18.04LTS 32bit', 'timestamp': True, 'hostname': 'wce', 'randomize_hostname': True, 'partition_plan': 'traditional', 'partition_map': 'msdos', 'cmdline': {'forcepae': None, 'acpi_enforce_resources': 'lax'}},
      {'id': 'ubuntu-18', 'filestem': 'mate1804', 'name': 'Ubuntu 18.04LTS with no payload', 'timestamp': True, 'efi_image': '.efi-512M.fat32.partclone.gz', 'partition_map': 'gpt', 'cmdline': {'acpi_enforce_resources': 'lax', 'nvme_core.default_ps_max_latency_us': '5500'}},
      {'id': 'wce-16', 'filestem': 'wce-mate16', 'name': 'WCE Ubuntu 16.04LTS', 'timestamp': True, 'ext4_version': '1.42', 'partition_map': 'gpt', 'partition_plan': 'traditional', 'hostname': 'wce', 'randomize_hostname': True, 'cmdline': {'acpi_enforce_resources': 'lax', 'forcepae': None}},
      {'id': 'triage', 'filestem': 'triage', 'name': 'Triage 64bit USB flash', 'timestamp': True, 'efi_image': '.efi-part-32M.fat32.partclone.gz', 'media': 'usb-flash', 'wce_share_url': '/usr/local/share/wce', 'cmdline': {'acpi_enforce_resources': 'lax', 'quiet': '_REMOVE_', 'splash': '_REMOVE_'}},
      {'id': 'lubuntu-18', 'filestem': 'lubuntu-1804', 'name': 'Lubuntu 18.04LTS', 'timestamp': True, 'efi_image': '.efi-512M.fat32.partclone.gz', 'partition_map': 'gpt'},
      {'id': 'test', 'filestem': 'test', 'name': 'Test WCE', 'timestamp': True, 'hostname': 'wce', 'randomize_hostname': True, 'partition_plan': 'traditional', 'partition_map': 'msdos', 'cmdline': {'forcepae': None, 'acpi_enforce_resources': 'lax'}}]



    pass

  def tearDown(self):
    shutil.rmtree(self.test_dir)
    pass

  def test_read_disk_image_types(self):
    image_types = read_disk_image_types()
    expected = self.image_types

    index = 0
    for image_type in image_types:
      del image_type['catalogDirectory']
      del image_type['index']
      self.assertEqual(image_type, expected[index])
      index += 1
      pass
    pass
  

  def test_read_disk_image_types_with_order(self):
    """wce-18 and wce-16 should become first and second of image types list."""
    with open(os.path.join(self.test_dir, "wce-disk-images", ".list-order"), "w") as list_order_file:
      print("wce-18", file=list_order_file)
      print("wce-16", file=list_order_file)
      pass
    
    image_types = read_disk_image_types()
    expected = self.image_types
    index = 0
    for expected in ["wce-18", "wce-16"]:
      self.assertEqual(image_types[index]['id'], expected)
      index += 1
      pass
    pass
  

  def test_get_disk_image(self):
    images = get_disk_images()
    expected = [ {'mtime': '<wild>', 'restoreType': 'wce-18', 'name': 'test1.partclone.gz', 'fullpath': "<random>", 'size': 4, 'subdir': 'wce-18', 'index': 0},
                 {'mtime': '<wild>', 'restoreType': 'wce-16', 'name': 'test2.partclone.gz', 'fullpath': "<random>", 'size': 4, 'subdir': 'wce-16', 'index': 1} ]
    index = 0
    for image in images:
      self.assertEqual(image['name'], expected[index]["name"])
      self.assertEqual(image['restoreType'], expected[index]["restoreType"])
      index += 1
      pass
    pass
  
  def test_get_file_system_from_source(self):
    self.assertEqual(get_file_system_from_source("a.ext4.partclone.gz"), "ext4")
    self.assertEqual(get_file_system_from_source("a.ext4.partclone"), None)
    self.assertEqual(get_file_system_from_source("a.partclone.gz"), None)
    pass

  def test_translate_disk_image_path(self):
    expected = [ {'fullpath': 'http://10.3.2.1:8080/wce/wce-disk-images/wce-18/test1.partclone.gz'},
                 {'fullpath': 'http://10.3.2.1:8080/wce/wce-disk-images/wce-16/test2.partclone.gz'} ]
    index = 0
    for disk_image in get_disk_images():
      self.assertEqual(expected[index]['fullpath'], translate_disk_image_name_to_url("http://10.3.2.1:8080/wce", disk_image["name"])['fullpath'])
      index += 1
      pass
    pass

if __name__ == '__main__':
  unittest.main()
