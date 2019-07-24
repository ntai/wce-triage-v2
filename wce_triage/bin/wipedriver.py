#!/usr/bin/python3

# I took a look at the all of disk wiping software I know on Linux.
# wipe, nwipe and scrub. They work but it's pretty hard to wire it
# up to web. Since all I need is equvalent of
# dd if=/dev/zero of=/dev/sdX bs=1M, I'll do this in script so I have
# control over the output.

import os, sys, subprocess
from wce_triage.bin.process_driver import *
from wce_triage.lib.util import *

if __name__ == "__main__":
  logging.basicConfig(level=logging.DEBUG,
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                      filename='/tmp/triage.log')

  if len(sys.argv) != 2:
    sys.stderr.write('wipe_disk.py <wiped>\n')
    sys.exit(1)
    pass
    
  device = sys.argv[1]
  if not is_block_device(device):
    sys.stderr.write("%s is not a block device.\n" % device)
    sys.exit(1)
    pass

  tlog = get_triage_logger()

  bin_name = "WIPE"
  processes = []
  pipes = []


  argv_zero = ['python3', '-m', 'wce_triage.bin.zerowipe', device]
  tlog.debug(' '.join(argv_zero))

  zero = subprocess.Popen(argv_zero, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  processes.append((argv_zero[0], zero))
  pipes.append(PipeInfo(argv_zero[0], zero, "stdout", zero.stdout))
  pipes.append(PipeInfo(argv_zero[0], zero, "stderr", zero.stderr))
  sys.exit(drive_process(bin_name, processes, pipes))
  pass
