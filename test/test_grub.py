import unittest
import tempfile
import shutil
import os

from wce_triage.const import *
from wce_triage.lib.grub import *


example_grub = """# If you change this file, run 'update-grub' afterwards to update
# /boot/grub/grub.cfg.
# For full documentation of the options in this file, see:
#   info -f grub -n 'Simple configuration'

GRUB_DEFAULT=0
GRUB_TIMEOUT_STYLE=hidden
GRUB_TIMEOUT=10
GRUB_DISTRIBUTOR=`lsb_release -i -s 2> /dev/null || echo Debian`
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
GRUB_CMDLINE_LINUX=""

export GRUB_CMDLINE_LINUX_DEFAULT_ALT="quiet splash"

# Uncomment to enable BadRAM filtering, modify to suit your needs
# This works with Linux (no patch required) and with any kernel that obtains
# the memory map information from GRUB (GNU Mach, kernel of FreeBSD ...)
#GRUB_BADRAM="0x01234567,0xfefefefe,0x89abcdef,0xefefefef"

# Uncomment to disable graphical terminal (grub-pc only)
#GRUB_TERMINAL=console

# The resolution used on graphical terminal
# note that you can use only modes which your graphic card supports via VBE
# you can see them in real GRUB with the command `vbeinfo'
#GRUB_GFXMODE=640x480

# Uncomment if you don't want GRUB to pass "root=UUID=xxx" parameter to Linux
#GRUB_DISABLE_LINUX_UUID=true

# Uncomment to disable generation of recovery mode menu entries
#GRUB_DISABLE_RECOVERY="true"

# Uncomment to get a beep at grub start
#GRUB_INIT_TUNE="480 440 1"
"""

result_grub = """# If you change this file, run 'update-grub' afterwards to update
# /boot/grub/grub.cfg.
# For full documentation of the options in this file, see:
#   info -f grub -n 'Simple configuration'

GRUB_DEFAULT=0
GRUB_TIMEOUT_STYLE=hidden
GRUB_TIMEOUT=10
GRUB_DISTRIBUTOR=`lsb_release -i -s 2> /dev/null || echo Debian`
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash wce_share=/usr/local/share/wce forcepae"
GRUB_CMDLINE_LINUX=""

export GRUB_CMDLINE_LINUX_DEFAULT_ALT="quiet splash wce_share=/usr/local/share/wce forcepae"

# Uncomment to enable BadRAM filtering, modify to suit your needs
# This works with Linux (no patch required) and with any kernel that obtains
# the memory map information from GRUB (GNU Mach, kernel of FreeBSD ...)
#GRUB_BADRAM="0x01234567,0xfefefefe,0x89abcdef,0xefefefef"

# Uncomment to disable graphical terminal (grub-pc only)
#GRUB_TERMINAL=console

# The resolution used on graphical terminal
# note that you can use only modes which your graphic card supports via VBE
# you can see them in real GRUB with the command `vbeinfo'
#GRUB_GFXMODE=640x480

# Uncomment if you don't want GRUB to pass "root=UUID=xxx" parameter to Linux
#GRUB_DISABLE_LINUX_UUID=true

# Uncomment to disable generation of recovery mode menu entries
#GRUB_DISABLE_RECOVERY="true"

# Uncomment to get a beep at grub start
#GRUB_INIT_TUNE="480 440 1"
"""

class Test_grub(unittest.TestCase):

  def setUp(self):
    self.maxDiff = None
    self.test_dir = tempfile.mkdtemp()
    self.test_file = os.path.join(self.test_dir, "grub")
    test_file = open(self.test_file, "w")
    test_file.write(example_grub)
    test_file.close()
    pass

  def tearDown(self):
    shutil.rmtree(self.test_dir)
    pass

  def test_make_efi_partition_plan(self):
    grub = grub_config(self.test_file)
    grub.open()

    for variable_name, variable in grub.variables.items():
      self.assertNotEqual(variable.line_no, None)
      pass

    grub.set_cmdline_option(const.wce_share, "/usr/local/share/wce")
    grub.set_cmdline_option(const.forcepae, None)

    updated, new_grub = grub.generate()
    self.assertEqual(result_grub, new_grub)
    self.assertTrue(updated)
    pass

  pass

if __name__ == '__main__':
  unittest.main()
