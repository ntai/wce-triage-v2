import os
import re
import subprocess

def get_ubuntu_release():
  release_re = re.compile(r'DISTRIB_RELEASE\s*=\s*(\d+\.\d+)')
  with open('/etc/lsb-release') as lsb_release_fd:
    for line in lsb_release_fd.readlines():
      result = release_re.search(line)
      if result:
        return result.group(1)
      pass
    pass
  return None


# Variables the setup steps rely on. sudo is often configured with
# "sudo: preserving the entire environment is not supported, '-E' is ignored",
# so these are handed to the child through /usr/bin/env instead.
SETUP_ENV_KEYS = [
  'GRUB_DISABLE_OS_PROBER',
  'GRUB_MENU_TITLE_ALT',
  'PATCHES',
  'PYTHONPATH',
  'TRIAGEPASS',
  'TRIAGEUSER',
  'WCE_DESKTOP',
  'WCE_KIOSK',
  'WCE_SERVER',
  'WCE_TRIAGE_DISK',
]


def sudo_run_module(package_name, env=None):
  """Run "python3 -m <package_name>" as root with the setup variables intact."""
  if env is None:
    env = os.environ.copy()
    pass
  assignments = ['%s=%s' % (key, env[key]) for key in SETUP_ENV_KEYS if key in env]
  args = ['sudo', '-H', 'env'] + assignments + ['python3', '-m', package_name]
  return subprocess.run(args, env=env)