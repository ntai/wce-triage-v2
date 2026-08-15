#!/usr/bin/python3
#
# Ubuntu desktop sessions are Wayland only now. SDL2 there creates its GL
# context through EGL, and the GLEW that Ubuntu ships initializes against GLX,
# so glewInit() fails and the application dies on startup. Colobot reports it
# as "An error occurred while initializing GLEW".
#
# Qt and GTK applications are fine - tested openscad and avogadro2, both link
# GLEW and both run under Wayland - so only SDL2 + GLEW needs the workaround:
# run those on Xwayland by setting SDL_VIDEODRIVER=x11.
#
# Rather than name applications, this finds them: any .desktop whose program
# links both libSDL2 and libGLEW gets an override in /usr/local/share, which
# XDG_DATA_DIRS searches before /usr/share. The packaged .desktop is left
# alone, so upgrades do not fight this and removing the override undoes it.
#
import os
import re
import shutil
import subprocess
import tempfile

SYSTEM_APPLICATIONS = '/usr/share/applications'
LOCAL_APPLICATIONS = '/usr/local/share/applications'

SDL_VIDEODRIVER = 'env SDL_VIDEODRIVER=x11 '

# sudo's secure_path leaves out the games directories, and that is exactly
# where the SDL applications live.
SEARCH_PATH = os.defpath + os.pathsep + os.pathsep.join(
  ['/usr/games', '/usr/local/games', '/usr/bin', '/usr/local/bin'])

exec_re = re.compile(r'^Exec\s*=\s*(.*)$')


def run(argv):
  if os.getuid() != 0:
    argv = ['sudo', '-H'] + argv
    pass
  return subprocess.run(argv)


def get_program(exec_value):
  """First token of an Exec= line, minus any leading env invocation."""
  argv = exec_value.split()
  while argv and ('=' in argv[0] or argv[0] == 'env'):
    argv = argv[1:]
    pass
  if not argv:
    return None
  return shutil.which(argv[0]) or shutil.which(argv[0], path=SEARCH_PATH)


def needs_xwayland(program):
  """True when the program uses SDL2 and GLEW together."""
  try:
    ldd = subprocess.run(['ldd', program], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
  except OSError:
    return False
  libraries = ldd.stdout.decode('iso-8859-1')
  return 'libSDL2' in libraries and 'libGLEW' in libraries


def patch_desktop_file(desktop_file):
  """Copy the .desktop to /usr/local, with every Exec line forced onto X11."""
  source = os.path.join(SYSTEM_APPLICATIONS, desktop_file)
  program = None
  patched = []

  with open(source, encoding='utf-8', errors='replace') as source_fd:
    for line in source_fd.read().splitlines():
      matched = exec_re.match(line)
      if matched:
        exec_value = matched.group(1)
        if program is None:
          program = get_program(exec_value)
          if program is None or not needs_xwayland(program):
            return False
          pass
        # Desktop Actions carry their own Exec lines. Patch them all.
        if not exec_value.startswith('env SDL_VIDEODRIVER'):
          line = 'Exec=' + SDL_VIDEODRIVER + exec_value
          pass
        pass
      patched.append(line)
      pass
    pass

  if program is None:
    return False

  print("%s uses SDL2 with GLEW. Forcing it onto Xwayland." % desktop_file)

  handle, temp_name = tempfile.mkstemp(suffix='.desktop')
  with os.fdopen(handle, 'w', encoding='utf-8') as temp_fd:
    temp_fd.write('\n'.join(patched) + '\n')
    pass
  run(['install', '-D', '-m', '0644', temp_name,
       os.path.join(LOCAL_APPLICATIONS, desktop_file)])
  os.unlink(temp_name)
  return True


if __name__ == "__main__":
  if not os.path.isdir(SYSTEM_APPLICATIONS):
    print("No %s. Nothing to patch." % SYSTEM_APPLICATIONS)
  else:
    patched_any = False
    for desktop_file in sorted(os.listdir(SYSTEM_APPLICATIONS)):
      if not desktop_file.endswith('.desktop'):
        continue
      if patch_desktop_file(desktop_file):
        patched_any = True
        pass
      pass

    if patched_any and shutil.which('update-desktop-database'):
      run(['update-desktop-database', LOCAL_APPLICATIONS])
      pass
    pass
  pass