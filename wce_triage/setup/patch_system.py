#!/usr/bin/env python3
#
import os, sys
if os.getuid() != 0:
  print("This script needs to run as root.")
  sys.exit(1)
  pass

PATCH_SRC = 'patches'
SYSTEM_ROOT = '/'

class patch_plan:
  def __init__(self, dir, file):
    self.dir = dir
    self.file = file
    pass

  def exec(self):
    tree = self.dir.split('/') # this should be a path delim..
    tree = tree[1:]
    tree.append(self.file)
    target = os.path.join(SYSTEM_ROOT, '/'.join(tree))
    source = self.dir+"/"+self.file
    if os.path.splitext(self.file)[1] == '.diff':
      subprocess.run( ['patch', target, source])
      pass
    else:
      # when you copy, make sure to copy the filemode
      print ( " copy: %s/%s --> %s" % (self.dir, self.file, target))
      subprocess.run( ['cp', '-p', source, target])
      subprocess.run( ['chown', 'root:root', target])
      pass
    pass
  
  pass


plans = []

def traverse_dir(dir):
  dirs = []
  for entity in os.listdir(dir):
    longpath = os.path.join(dir, entity)
    if os.path.isdir(longpath):
      dirs.append(longpath)
    elif os.path.isfile(longpath):
      plans.append(patch_plan(dir, entity))
      pass
    pass

  for subdir in dirs:
    traverse_dir(subdir)
    pass
  pass

traverse_dir(PATCH_SRC)

for plan in plans:
  plan.exec()
  pass
