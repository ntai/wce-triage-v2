#!/usr/bin/env python3
#
import os, subprocess
import json
import re


SYSTEM_ROOT = '/'

class patch_plan:
  def __init__(self, rootdepth, direc, file):
    self.rootdepth = rootdepth
    self.dir = direc
    self.file = file
    self.plans = []
    self.plan()
    pass

  def plan(self):
    tree = self.dir.split('/') # this should be a path delim..
    tree = tree[1:]
    tree.append(self.file)
    target = os.path.join(SYSTEM_ROOT, '/'.join(tree[self.rootdepth-1:]))
    source = self.dir+"/"+self.file
    if os.path.splitext(self.file)[1] == '.diff':
      # remove .diff at the end.
      target = target[:-5]
      self.plans.append("Patch %s with %s" % (target, source))
      self.plans.append(['patch', '--forward', target, source])
      pass
    else:
      # when you copy, make sure to copy the filemode
      self.plans.append("copy: %s/%s --> %s" % (self.dir, self.file, target))
      target_dir = os.path.dirname(target)

      self.plans.append(['mkdir', '-p', target_dir])

      # FIXME: metadata manipulation needs implementation.
      metadata_file = os.path.join(self.dir, ".metadata.json")
      metadata = {}
      if os.path.exists(metadata_file):
        with open(metadata_file) as metadata_fd:
          metadata = json.load(metadata_fd)
          pass
        pass
      if metadata:
        if "mode" in metadata:
          os.chmod(self.dir, int(metadata["mode"], 8))
          pass
        pass

      self.plans.append(['cp', '-p', source, target])
      try:
        dirstat = os.stat(os.path.dirname(target_dir))
        self.plans.append(['chown', "%d:%d" % (dirstat.st_uid,dirstat.st_gid), target])
      except FileNotFoundError:
        # 
        pass

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
    self.rootdepth = 0
    pass

  def traverse_dir(self, direc):
    self.rootdepth = len(direc.split('/'))
    self._traverse_dir(direc)
    pass

  def _traverse_dir(self, direc):
    dirs = []
    for entity in os.listdir(direc):
      longpath = os.path.join(direc, entity)
      if os.path.isdir(longpath):
        dirs.append(longpath)
      elif os.path.isfile(longpath):
        if entity.endswith('.metadata.json'):
          continue
        self.plans.append(patch_plan(self.rootdepth, direc, entity))
        pass
      pass

    for subdir in dirs:
      self._traverse_dir(subdir)
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


def get_ubuntu_release():
  release_re = re.compile( 'DISTRIB_RELEASE\s*=\s*(\d+\.\d+)' )
  with open('/etc/lsb-release') as lsb_release_fd:
    for line in lsb_release_fd.readlines():
      result = release_re.search(line)
      if result:
        return result.group(1)
      pass
    pass
  return None

if __name__ == "__main__":
  patch_dir = os.path.dirname(__file__) 
  patch_source_root = os.path.join(patch_dir, 'patches', get_ubuntu_release())
  COMMON_PATCH_SRC = os.path.join(patch_source_root, "common")
  VARIANT_PATCH_SRC = os.path.join(patch_source_root, os.environ['PATCHES'])

  builder = plan_builder()
  builder.traverse_dir(COMMON_PATCH_SRC)
  builder.traverse_dir(VARIANT_PATCH_SRC)
  builder.explain()
  if os.getuid() == 0:
    builder.execute()
    #
    subprocess.run(['update-grub'])
    subprocess.run(['update-initramfs', '-u'])
  else:
    print("For non-root, this is explanation only.")
    pass
  pass
