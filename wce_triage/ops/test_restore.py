import os, sys, subprocess, pickle, _pickle, time

if __name__ == "__main__":
  
  restore = subprocess.Popen(['python3', '-m', 'wce_triage.ops.restore_image_runner'] + sys.argv[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  for lines in restore.stdout.readlines():
    sys.stdout.write(data)
    sys.stdout.flush()
    pass
  pass
