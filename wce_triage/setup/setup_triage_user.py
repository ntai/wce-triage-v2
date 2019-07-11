#!/usr/bin/python3
#
import os, sys, subprocess

TRIAGEUSER=os.environ.get("TRIAGEUSER", "triage")

if __name__ == "__main__":
  #
  # Be able to start the tty by user
  subprocess.run(['sudo', 'usermod', '-a', '-G', 'tty,audio,video', TRIAGEUSER])

  # and, be able to start X by user
  subprocess.run(['sudo', 'chmod', 'ug+s', '/usr/lib/xorg/Xorg'])
  pass

