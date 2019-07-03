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


def get_disk_images():
  # Dedup the same file name
  images = {}
  for dir in get_disk_image_directories():
    for file in os.listdir(dir):
      if file.endswith(".partclone.gz"):
        images[file] = os.path.join(dir, file)
        pass
      pass
    pass

  result = []
  for file, filepath in images.items():
    filestat = os.stat(filepath)
    mtime = datetime.datetime.fromtimestamp(filestat.st_mtime)
    fattr = { "mtime": mtime.strftime('%Y-%m-%d %H:%M'),
              "name": file,
              "fullpath": filepath,
              "size": filestat.st_size }
    result.append(fattr)
    pass

  return result

def is_block_device(path):
  path_stat = os.stat(path)
  return stat.S_ISBLK(path_stat.st_mode)


#
if __name__ == "__main__":
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
