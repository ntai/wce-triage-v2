#!/usr/bin/python3
#
import os, subprocess

TRIAGEUSER = os.environ.get("TRIAGEUSER", "wce")
TRIAGEPASS = os.environ.get('TRIAGEPASS', 'wce123')

if __name__ == "__main__":
  #
  # Be able to start the tty by user
  #
  subprocess.run(['sudo', '-H', 'useradd', TRIAGEUSER, '-U', '-m', '-p', TRIAGEPASS, '-s' '/bin/bash', '-G', 'sudo'])
  subprocess.run(['sudo', '-H', 'usermod', '-a', '-G', 'tty,audio,video', TRIAGEUSER])

  # and, be able to start X by user
  subprocess.run(['sudo', 'chmod', 'ug+s', '/usr/lib/xorg/Xorg'])
  pass

