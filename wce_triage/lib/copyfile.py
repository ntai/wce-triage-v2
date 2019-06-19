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

