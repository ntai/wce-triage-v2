import sys, subprocess

if __name__ == "__main__":
  
  restore = subprocess.Popen([sys.executable, '-m', 'wce_triage.ops.restore_image_runner'] + sys.argv[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  for line in restore.stdout.readlines():
    sys.stdout.write(line.decode('iso-8859-1'))
    sys.stdout.flush()
    pass
  pass
