import uuid, os, subprocess, datetime, select, stat
import urllib.parse


def safe_string(piece):
  if piece:
    if isinstance(piece, bytes):
      return piece.decode('utf-8')
    return str(piece)
  return ""


def drain_pipe(pipe, encoding='utf-8', timeout=0.5):
  read_set = [pipe]
  selecting = True
  while selecting:
    selecting = False
    try:
      rlist, wlist, xlist = select.select(read_set, [], [], timeout)

      if pipe in rlist:
        chunk = os.read(pipe.fileno(), 4096)
        if chunk == b'':
          return None
        return chunk.decode(encoding)
      pass
    except select.error as exc:
      if exc.args[0] == errno.EINTR:
        selecting = True
        pass
      else:
        raise
      pass
    pass
  return ""


def drain_pipe_completely(pipe, encoding='utf-8'):
  read_set = [pipe]
  data = ""
  draining = True
  while draining:
    chunk = drain_pipe(pipe, encoding=encoding)
    if chunk is None:
      draining = False
      break
    elif len(chunk):
      data = data + chunk
      pass
    pass
  return data


def uuidgen():
  return str(uuid.uuid1())


def get_filename_stem(p):
  basename = os.path.basename(p)
  while 1:
    ext = ""
    try:
      basename, ext = os.path.splitext(basename)
    except:
      pass
    if ext == "":
      break
    pass
  return basename

def read_file(filepath):
  content = None
  try:
    f = open(filepath)
    content = f.read()
    f.close()
  except:
    pass
  return content
    

def compare_files(file1, file2):
  return read_file(file1) == read_file(file2)


# --------------------------------------------------------------------------------
def mount_iso_file(iso_file, iso_mount_point):
  if not os.path.exists(iso_mount_point):
    os.mkdir(iso_mount_point)
    pass
  mount = subprocess.Popen(["mount", "-o", "loop", iso_file, iso_mount_point], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  (out, err) = mount.communicate()
  pass


def unmount_iso_file(iso_file, iso_mount_point):
  umount = subprocess.Popen(["umount", iso_mount_point], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  (out, err) = umount.communicate()
  os.rmdir(iso_mount_point)
  pass

#
def find_disk_device_files(devpath):
  result = []
  for letter in "abcdefghijklmnopqrstuvwxyz":
    device_file = devpath + letter
    if os.path.exists(device_file):
      result.append(device_file)
      pass
    pass
  return result


#
# Known decompressors
# The first of tuple is the decompression command.
# The second of tuple is an option to use the stdin
# as input.
#
decomps = { ".7z":  ( [ "7z", "e", "-so" ], None ),
            ".xz":  ( [ "unxz" ], ["-c"] ),
            ".lzo": ( [ "lzop", "-d"], ["-c"] ),
            ".gz":  ( [ "gunzip" ], ["-c"] ) }

def get_file_decompression_app(path):
  ext = ""
  try:
    ext = os.path.splitext(path)[1]
  except:
    pass
  return decomps.get(ext)


# After all, gzip/pigz wins the performnce
# and compression balance. xz compresses touch better but
# it takes so much longer. You can convert the compressor
# if there is a good reason (hence, the decomp takes more
# options but for compression from here, gzip/pigz is it.

def get_file_compression_app(path):
  return ( ["pigz", "-7" ], [] )

#
#
#
def get_transport_scheme(urlpath):
  transport_scheme = None
  try:
    transport_scheme = urllib.parse.urlsplit(urlpath).scheme
  except:
    pass
  return transport_scheme


# gets the potential directories to look for disk images
def get_disk_image_directories():
  import psutil
  dirs = []

  for part in psutil.disk_partitions():
    for subdir in [ ".", "image", "var/lib/www", "usr/local/share/wce" ]:
      path = os.path.join(part.mountpoint, subdir, 'wce-disk-images')
      if os.path.exists(path) and os.path.isdir(path):
        dirs.append(path)
        pass
      pass
    pass
  return dirs


#
# 
#
def get_disk_images():
  '''scans the known drectories for disk image and returns the list of disk images

    :arg none

    :returns: list of dict instances. 
      mtime: file modify time
      restoreType: keyword for restore type. [wce|wce-16|triage|clone]
                   The restore type is nothing more than the name of directory, and
                   should match exactly to the restore type.
      name: filename - this is shown to the user.
      size: file size
      fullpath: the full path.

    ..note the entries are deduped by the filename so if two directories
           contain the same file name, only one is pikced.
  '''
  # Dedup the same file name
  images = {}
  for dir in get_disk_image_directories():
    for direntry in os.listdir(dir):
      longpath = os.path.join(dir, direntry)
      if direntry.endswith(".partclone.gz"):
        images[direntry] = (direntry, "", longpath)
        pass
      if os.path.isdir(longpath):
        for direntryinsubdir in os.listdir(longpath):
          if direntryinsubdir.endswith(".partclone.gz"):
            images[direntryinsubdir] = (direntryinsubdir, direntry, os.path.join(longpath, direntryinsubdir))
            pass
          pass
        pass
      pass
    pass

  result = []
  for filename, image in images.items():
    fname, subdir, fullpath = image
    filestat = os.stat(fullpath)
    mtime = datetime.datetime.fromtimestamp(filestat.st_mtime)
    fattr = { "mtime": mtime.strftime('%Y-%m-%d %H:%M'),
              "restoreType" : subdir,
              "name": filename,
              "fullpath": fullpath,
              "size": filestat.st_size }
    result.append(fattr)
    pass

  return result

def is_block_device(path):
  path_stat = os.stat(path)
  return stat.S_ISBLK(path_stat.st_mode)

import logging
logfileout = None

def get_triage_logger():
  global logfileout

  tlog = logging.getLogger('triage')
  return tlog


# Get the test password that you can feed to sudo
# IOW, the output is not string, but bytes
def get_test_password():
  password = os.environ.get('WCE_TEST_PASSWORD')
  if password is None:
    password = "wce123\n"
    pass
  else:
    password = password + "\n"
    pass
  return password.encode('iso-8859-1')

#
def get_ip_addresses():
  ip_route = subprocess.run('ip route', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  entries = ip_route.stdout.decode('iso-8859-1').splitlines()[0].strip().split(' ')
  return (entries[2], entries[8])


#
if __name__ == "__main__":
  print ('my ip addr = ' + get_my_ip_address())

  for diskimage in get_disk_images():
    print (diskimage)
    pass
  

  sleep = subprocess.Popen("sleep 5", shell=True, stdout=subprocess.PIPE)
  
  for i in range(1, 10):
    start_time = datetime.datetime.now()
    drain_pipe(sleep.stdout, timeout=0.5)
    end_time = datetime.datetime.now()
    dt = end_time - start_time
    print(dt.total_seconds())
    pass
  pass
