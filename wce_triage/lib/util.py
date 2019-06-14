import uuid, os

def safe_string(piece):
  if piece:
    if isinstance(piece, bytes):
      return piece.decode('utf-8')
    return str(piece)
  return ""

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

def write_text_to_triage(text):
  triage_output = open(triage_txt, "a+")
  triage_output.write(text)
  triage_output.close()
  pass

def write_exception_to_triage(exc):
  text = traceback.format_exc(exc)
  write_text_to_triage(text)
  pass
    

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
# File copying util
#

class node:
  def __init__(self, parent, name):
    self.total_size = 0
    self.file_size = 0
    self.parent = parent
    self.files = []
    self.dirs = []
    self.path = None
    self.name = name
    self.destination = None
    pass

  def get_full_path(self):
    if not self.path:
      self.path = os.path.join(self.parent.get_full_path(), self.name)
      pass
    return self.path

  def walk(self):
    path = self.get_full_path()
    for entry in os.listdir(path):
      entry_path = os.path.join(path, entry)
      if os.path.isfile(entry_path):
        self.file_size = self.file_size + os.path.getsize(entry_path)
        self.files.append(entry)
        pass
      elif os.path.isdir(entry_path):
        self.dirs.append(node(self, entry))
        pass
      pass
    for dir in self.dirs:
      dir.walk()
      pass
    pass

  def get_total_file_size(self):
    size = self.file_size
    for dir in self.dirs:
      size = size + dir.file_size
      pass
    return size


  def set_destination(self, destnode, walk):
    if self.destination != None:
      return
    self.destination = destnode
    self.destination.total_size = self.total_size
    self.destination.file_size = self.file_size
    self.destination.files = self.files
    if walk:
      for dir in self.dirs:
        partner = node(destnode, dir.name)
        self.destination.dirs.append(partner)
        dir.set_destination(partner, True)
        pass
      pass
    pass


  def print_plan(self, level):
    print("%s%s -> %s" % (indentstr[0:level*2], self.get_full_path(), self.destination.get_full_path()))
    print("%sTotal size: %d" % (indentstr[0:level*2], self.file_size))
    for file in self.files:
      print("%s%s" % (indentstr[0:level*2], file))
      pass
    for dir in self.dirs:
      dir.print_plan(level+1)
      pass
    pass


  def get_destination_path(self, file):
    return os.path.join(self.get_full_path(), file)


  def generate_plan(self):
    plan = []
    src = self.get_full_path()
    dst = self.destination.get_full_path()
    plan.append(('dir', src, dst, 0))
    for file in self.files:
      srcfile = os.path.join(src, file)
      dstfile = self.destination.get_destination_path(file)
      plan.append(('copy', srcfile, dstfile, os.path.getsize(srcfile)))
      pass
    for dir in self.dirs:
      plan = plan + dir.generate_plan()
      pass
    return plan
  
  pass


class root_node(node):
  def __init__(self, path):
    self.total_size = 0
    self.file_size = 0
    self.parent = None
    self.files = []
    self.dirs = []
    self.path = path
    self.name = None
    self.destination = None
    pass
    

  def get_full_path(self):
    return self.path

  def print_plan(self, level):
    node.print_plan(self, level)
    print("Grand total: %d" % self.get_total_file_size())
    pass

  pass


class syslinux_node(node):
  def __init__(self, parent, name):
    self.total_size = 0
    self.file_size = 0
    self.parent = parent
    self.files = []
    self.dirs = []
    self.path = None
    self.name = name
    self.destination = None
    pass

  def get_destination_path(self, file):
    if file == "isolinux.cfg":
      return os.path.join(self.get_full_path(), "syslinux.cfg")
    elif file == "isolinux.bin":
      return os.path.join(self.get_full_path(), "syslinux.bin")
    return os.path.join(self.get_full_path(), file)
    pass

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

def wait_for_disk_insertion():
  current_disks = find_disk_device_files("/dev/hd") + find_disk_device_files("/dev/sd")
  while True:
    time.sleep(2)
    new_disks = find_disk_device_files("/dev/hd") + find_disk_device_files("/dev/sd")
    if len(current_disks) < len(new_disks):
      break
    if len(current_disks) > len(new_disks):
      print( "Disk disappeared")
      pass
    current_disks = new_disks
    pass
  pass


def get_file_decompression_app(path):
  ext = ""
  try:
    ext = os.path.splitext(path)[1]
  except:
    pass

  if ext == ".7z":
    decomp = "7z e -so"
  elif ext == ".gz":
    decomp = "gunzip -c"
  elif ext == ".xz":
    decomp = "unxz -c"
  elif ext == ".partclone":
    # aka no compression
    decomp = "cat"
  elif ext == ".lzo":
    decomp = "lzop -dc"
  else:
    decomp = "gunzip -c"
    pass
  return decomp

def get_file_compression_app(path):
  comp = None
  try:
    ext = os.path.splitext(disk.imagename)[1]
  except:
    pass
  if ext == ".7z":
    comp = "p7zip"
  elif ext == ".gz":
    comp = "pigz -9"
  elif ext == ".xz":
    comp = "xz --stdout"
  elif ext == ".partclone":
    # aka no compression
    comp = "cat"
  elif ext == ".lzo":
    comp = "lzop -c"
  else:
    comp = "cat"
    pass
  return comp


def get_disk_image_directories():
  import psutil
  dirs = []

  for part in psutil.disk_partitions():
    for subdir in [ ".", "image", "var/lib/www" ]:
      path = os.path.join(part.mountpoint, subdir, 'wce-disk-images')
      if os.path.exists(path) and os.path.isdir(path):
        dirs.append(path)
        pass
      pass
    pass
  return dirs


def get_disk_images():
  images = {}
  for dir in get_disk_image_directories():
    for file in os.listdir(dir):
      if file.startswith("wce-") and file.endswith(".tar.gz"):
        images[file] = os.path.join(dir, file)
        pass
      pass
    pass
  return images
      
