#!/usr/bin/env python3
import os, sys, re

menuentry_start = "menuentry"

def extract_menuentry(infile):
  in_menuentry = False
  for line in infile.readlines():
    if in_menuentry:
      if line.strip() == "}":
        in_menuentry = False
        print(line.rstrip())
        pass
      else:
        print(line.rstrip())
        pass
      pass
    else:
      if line.startswith(menuentry_start):
        in_menuentry = True
        match = re.search(r"menuentry '[^']+' (.*)", line)
        print("menuentry '%s' %s" % (os.environ.get('GRUB_ALT_MENU_TITLE', 'Ubuntu Alternate'), match.group(1)))
        pass
      pass
    pass
  pass


if __name__ == "__main__":
  extract_menuentry(sys.stdin)
  pass
