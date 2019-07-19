#!/usr/bin/env python3
#
import os, sys

patch_dir = os.path.dirname(__file__)
PATCH_SRC = os.path.join(patch_dir, 'patches', os.environ['PATCHES'])
SYSTEM_ROOT = '/'

class patch_plan:
  def __init__(self, dir, file):
    self.dir = dir
    self.file = file
    self.plans = []
    self.plan()
    pass

  def plan(self):
    tree = self.dir.split('/') # this should be a path delim..
    tree = tree[1:]
    tree.append(self.file)
    target = os.path.join(SYSTEM_ROOT, '/'.join(tree))
    source = self.dir+"/"+self.file
    if os.path.splitext(self.file)[1] == '.diff':
      self.plans.append("Patch %s with %s" % (target, source))
      self.plans.append(['patch', target, source])
      pass
    else:
      # when you copy, make sure to copy the filemode
      self.plans.append("copy: %s/%s --> %s" % (self.dir, self.file, target))
      self.plans.append(['cp', '-p', source, target])
      self.plans.append(['chown', 'root:root', target])
      pass
    pass
  
  def explain(self):
    for plan in self.plans:
      if isinstance(plan, str):
        print (plan)
        pass
      elif isinstance(plan, list):
        print (' '.join(plan))
        pass
      pass
    pass

  def exec(self):
    for plan in self.plans:
      if isinstance(plan, list):
        subprocess.run(plan)
        pass
      pass
    pass
  pass


class plan_builder:
  def __init__(self):
    self.plans = []
    pass

  def traverse_dir(self, dir):
    dirs = []
    for entity in os.listdir(dir):
      longpath = os.path.join(dir, entity)
      if os.path.isdir(longpath):
        dirs.append(longpath)
      elif os.path.isfile(longpath):
        self.plans.append(patch_plan(dir, entity))
        pass
      pass

    for subdir in dirs:
      self.traverse_dir(subdir)
      pass
    pass

  def explain(self):
    for plan in self.plans:
      plan.explain()
      pass
    pass

  def execute(self):
    for plan in self.plans:
      plan.exec()
      pass
    pass
  pass

if __name__ == "__main__":
  builder = plan_builder()
  builder.traverse_dir(PATCH_SRC)
  builder.explain()
  if os.getuid() == 0:
    builder.execute()
  else:
    print("For non-root, this is explanation only.")
    pass
  pass
