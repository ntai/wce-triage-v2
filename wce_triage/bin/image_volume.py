#
# Image volume (aka unloading)
#
# This is used by runner.
#
# The status goes to the stderr. To make things simple, all of status
# is prefixed and each status is a single line.
#
import os, sys, subprocess, urllib

import urllib.parse

from ..lib.util import is_block_device, get_file_compression_app

from ..bin.process_driver import drive_process, PipeInfo

def save_disk(source, dest, filesystem=None, encoding='iso-8859-1'):
  if not is_block_device(source):
    return 1

  partclone_path = os.path.join('/', 'usr', 'sbin', 'partclone.%s' % filesystem)
  if not os.path.exists(partclone_path):
    print(partclone_path + " does not exist.")
    return 1

  # compressor to use (gzip!)
  comp = get_file_compression_app(dest)

  # curl
  parsed = urllib.parse.urlsplit(dest)
  if parsed.scheme:
    remotedest = urllib.parse.urljoin(dest, ".")
    
    addtions = []

    if parsed.query:
      params = urllib.parse.parse_qs(parsed.query)
      user = params.get('user')[0]
      password = params.get('password')[0]
      if user and password:
        addtions = [ "--user", "%s:%s" % (user, password) ]
        pass
      pass
      
    remotedest = urllib.parse.urlunsplit(parsed._replace(query="", fragment=""))
    # the input is always stdin
    argv_curl = [ "curl", "-s", "-T", "-", remotedest] + addtions
    pass
  else:
    argv_curl = None
    pass

  # When the compessor is used, it always reads from partclone's stdout
  # The compressor output is always a pipe, to actual file, or curl
  if comp:
    argv_comp = comp[0] + comp[1]
    pass
  else:
    argv_comp = None
    # Let partclone write to the local file.
    pass

  # When compressor or curl exists, partclone outputs to stdout.
  # When this is standalone, then, the actual file.
  # If the destination is stdout, it's still goes through compressor.
  if argv_comp or argv_curl or dest == '-':
    partclone_output = "-"
    partclone_stdout = subprocess.PIPE
  else:
    partclone_output = dest
    partclone_stdout = None
    pass

  # partclone
  argv_partclone = [ partclone_path, "-f", "2", "-c", "-L", "-", "-s", source, "-o", partclone_output ]

  # wire up the apps.
  pipes = []
  processes = []
  
  # parclone -- The standard out is either a pipe to compressor, or nothing.
  # If the output is file or fifo, this should open the output.
  partclone = subprocess.Popen(argv_partclone, stdout=partclone_stdout, stderr=subprocess.PIPE)
  processes.append((argv_partclone[0], partclone))
  pipes.append(PipeInfo("partclone", partclone, "stderr", partclone.stderr))

  # Now the compressor.
  # Input is always the partclone's stdout when the compressor exists.
  if argv_comp or dest == '-':
    if argv_curl:
      comp_stdout = subprocess.PIPE
    else:
      if dest == '-':
        comp_stdout = sys.stdout
      else:
        comp_stdout = open(dest, "wb")
        pass
      pass
    comp = subprocess.Popen(argv_comp, stdin=partclone.stdout, stdout=comp_stdout, stderr=subprocess.PIPE)
    processes.append((argv_comp[0], comp))
    pipes.append(PipeInfo(argv_comp[0], comp, "stderr", comp.stderr))
    pass
  else:
    comp = None
    pass

  # Start curl
  if argv_curl:
    curl_input = comp.stdout if comp else partclone.stdout
    print ("IMAGER: Exec " + " ".join(argv_curl))
    curl = subprocess.Popen(argv_curl, stdin=curl_input, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processes.append(("curl", curl))
    # Curl's stdout/err not used at all. Listen to both.
    pipes.append(PipeInfo("curl", curl, "stdout", curl.stdout))
    pipes.append(PipeInfo("curl", curl, "stderr", curl.stderr))
    pass
  else:
    curl = None
    pass

  # all the processes are up. Drive them.
  return drive_process("IMAGER", processes, pipes)


if __name__ == "__main__":
  if len(sys.argv) != 4:
    sys.stderr.write('''image_volume.py <source> [ext4|fat32] <dest>\n  source: device file\n  dest: URL [?user=<usename>&password=<password>] or '-' for stdout\n''')
    sys.exit(1)
    pass
    
  if not is_block_device(sys.argv[1]):
    sys.stderr.write("%s is not a block device.\n" % sys.argv[1])
    sys.exit(1)
    pass
  sys.exit(save_disk(sys.argv[1], sys.argv[3], filesystem=sys.argv[2]))
  
