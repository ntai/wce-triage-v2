import unittest
from wce_triage.components import cpu as cpu
from wce_triage.components import memory as memory
from wce_triage.components import optical_drive as optical_drive

class Test_components(unittest.TestCase):

  def test_cpu(self):
    cpu_type = cpu.detect_cpu_type()
    self.assertEqual(cpu_type.cpu_class, 5)
    self.assertGreater(cpu_type.cores, 1)
    self.assertGreater(cpu_type.speed, 0)
    pass

  def test_memory(self):
    mem = memory.detect_memory()
    # Memory type, etc runs dmidecode and requires root.
    self.assertGreater(len(mem.slots), 0)
    self.assertGreater(mem.total, 0)
    pass

  def test_optical_drives(self):
    opts = optical_drive.detect_optical_drives()
    self.assertGreater(len(opts), 0)
    opt = opts[0]
    #self.assertTrue(opt.dvd)
    pass

if __name__ == '__main__':
  unittest.main()
