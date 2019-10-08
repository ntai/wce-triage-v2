
import re
import sys

#
# GRUB_CMDLINE=""
# GRUB_CMDLINE_LINUX_DEFAULT=""
# export GRUB_CMDLINE_LINUX_DEFAULT_ALT="wce_share=FOO"
#

def grub_set_wce_share(grub_file, wce_share):
  grub_fd = open(grub_file, "r")
  grubcfg = grub_fd.read()
  grub_fd.close()

  cmdline_re_list = [ re.compile('(export\s+){{0,1}}({tag})="([^"]*)"'.format(tag=tag)) for tag in [ 'GRUB_CMDLINE_LINUX_DEFAULT', 'GRUB_CMDLINE_LINUX_DEFAULT_ALT' ]]
  opt_re = re.compile('(\w+)=(.*)')

  updated = False
  grubcfg_lines = grubcfg.splitlines()
  for i_line in range(len(grubcfg_lines)):
    line = grubcfg_lines[i_line][:]
    changed = False
    for cmdline_re in cmdline_re_list:
      match = cmdline_re.search(line)
      if match:
        new_opt = "wce_share=" + wce_share
        cmdline = match.group(3)
        options = cmdline.split(' ')
        for i_opt in range(len(options)):
          option = options[i_opt]
          tag_value = opt_re.match(option)
          if tag_value:
            if tag_value.group(1) == "wce_share":
              changed = True
              options[i_opt] = new_opt
              pass
            pass
          pass

        if not changed:
          options.append(new_opt)
          pass
        line = (match.group(1) if match.group(1) else '')  + match.group(2) + '="' + ' '.join(options) + '"'
        pass
      pass

    if line != grubcfg_lines[i_line]:
      grubcfg_lines[i_line] = line
      updated = True
      pass
    pass
  return (updated, '\n'.join(grubcfg_lines))

if __name__ == "__main__":
  filename = "/etc/default/grub"
  if len(sys.argv) > 1:
    filename = sys.argv[1]
    pass
  print( grub_set_wce_share(filename, "/usr/local/share/wce")[1])
  pass
