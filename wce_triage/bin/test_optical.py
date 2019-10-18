#
# test optical
#
# good/bad is printed in json.
# Since thing this does is too simple, I'll do kind of one-off.
#
import os, sys, subprocess, urllib, datetime, traceback

import urllib.parse
from collections import deque

from ..lib.util import *
from ..lib.timeutil import *
from .process_driver import *

tlog = init_triage_logger()

import json

def reply_result(result):
  jata = json.dumps( { "event": "triageupdate", "runMessage": result } )
  tlog.debug(jata)
  print(jata)
  sys.stdout.flush()
  pass

def deltatime(start, end):
  return round(in_seconds(end - start), 1)

# sadistic?
def check_child_directory(path):
  for entry in os.listdir(path):
    what = os.path.join(path, entry)
    if os.path.isdir(what):
      check_child_directory(what)
      pass
    pass
  pass


def unmount(password, mountpoint):
  umount = subprocess.Popen(['sudo', '-H', '-S', 'umount', mountpoint], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  try:
    mount.communicate(password, timeout=3)
  except Exception as exc:
    error_message = traceback.format_exc()
    tlog.info(error_message)
    pass
  pass

def test_optical(password, source, encoding='iso-8859-1'):
  tlog.debug("optical test started for " + source)
  if not is_block_device(source):
    reply_result({"component": "Optical drive",
                  "result": False,
                  "device": source,
                  "runMessage": "Device %s is not a block device." % source})
    return 1

  mountpoint = "/tmp/wcetriage.optest%s" % source
  try:
    os.makedirs(mountpoint, exist_ok=True)
  except Exception as exc:
    reply_result({"component": "Optical drive",
                  "result": False,
                  "device": source,
                  "runMessage": "Failed creating mount point %s" % mountpoint})
    return 1

  error_message = ""
  start_time = datetime.datetime.now()
  mount = None

  all_the_messages = []
  argv = ['sudo', '-H', '-S', 'mount', source, mountpoint]
  mount = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out = ''
  err = ''
  try:
    (out, err) = mount.communicate(password, timeout=120)
    pass
  except Exception as exc:
    error_message = traceback.format_exc()
    end_time = datetime.datetime.now()
    reply_result({"component": "Optical drive",
                  "result": False,
                  "runMessage" : "The device %s failed to mount." % source,
                  "verdict" : [error_message, out.decode('iso-8859-1'), err.decode('iso-8859-1')],
                  "device": source,
                  "elapseTime": deltatime(start_time, end_time)})
    unmount(password, source)
    return 1

  if out:
    all_the_messages.append(out.decode('iso-8859-1'))
    pass
  if err:
    all_the_messages.append(err.decode('iso-8859-1'))
    pass
  end_time = datetime.datetime.now()

  if mount and mount.returncode and mount.returncode != 0:
    all_the_messages.append(error_message)
    reply_result({"component": "Optical drive",
                  "result": False,
                  "runMessage" : "The device %s failed to mount." % source,
                  "verdict" : all_the_messages,
                  "device": source,
                  "elapseTime": deltatime(start_time, end_time)})
    unmount(password, source)
    return 1

  okay = False
  error_message = ""

  try:
    check_child_directory(mountpoint)
    okay = True
  except Exception as exc:
    error_message = traceback.format_exc()
    pass
  end_time = datetime.datetime.now()

  if error_message:
    all_the_messages.append(error_message)
    pass

  result = { "device": source, "elapseTime": deltatime(start_time, end_time) }
  reply_result({"component": "Optical drive",
                "result": okay,
                "runMessage" : "The device %s passed the test." % source,
                "verdict": all_the_messages,
                "device": source,
                "elapseTime": deltatime(start_time, end_time)})
  unmount(password, source)
  return 0


if __name__ == "__main__":
  if len(sys.argv) != 2:
    sys.stderr.write('test_optical.py <source>\n  source: optical device file\n')
    sys.exit(1)
    pass
    
  sys.exit(test_optical(get_test_password(), sys.argv[1]))
  pass

