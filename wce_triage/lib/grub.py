
import re
import sys
import typing

from .kernel_flags import kernel_flags
from ..const import const

#
# GRUB_CMDLINE=""
# GRUB_CMDLINE_LINUX_DEFAULT=""
# export GRUB_CMDLINE_LINUX_DEFAULT_ALT="wce_share=FOO"
#

class grub_variable:
  tag: str

  def __init__(self, tag: str):
    self.tag = tag
    self.rex = '(export\s+){{0,1}}({tag})="([^"]*)"'.format(tag=tag)
    self.variable_re = re.compile(self.rex)
    self.cmdline = None
    self.flags = None
    self._line_no = None
    pass

  def parse_line(self, line, line_no):
    if len(line) == 0 or line[0] == '#':
      return False
    matched = self.variable_re.search(line)
    if matched:
      self.line = line
      self._line_no = line_no
      self.prefix = matched.group(1)
      self.prefix = self.prefix if self.prefix else ""
      self.cmdline = matched.group(3)
      self.flags = kernel_flags(self.cmdline)
      return True
    return False

  def set_cmdline_option(self, tag, value):
    if not self._line_no:
      return
    if value == const._REMOVE_:
      self.flags.remove_flag(tag)
    elif value:
      self.flags.set_tag_value(tag, value)
    else:
      self.flags.set_flag(tag)
      pass
    pass
  
  def remove_option(self, tag):
    self.flags.remove_flag(tag)
    pass
  
  @property
  def line_no(self):
    return self._line_no

  def generate_line(self):
    return '{}{}="{}"'.format(self.prefix, self.tag, self.flags.get_cmdline())

  pass


class grub_config:
  """grub.cfg manipulation"""
  def __init__(self, filename):
    self.filename = filename
    self.variables = {}
    for variable in [ grub_variable('GRUB_CMDLINE_LINUX_DEFAULT'), grub_variable('GRUB_CMDLINE_LINUX_DEFAULT_ALT')]:
      self.variables[variable.tag] = variable
      pass
    self.override_map = {}
    self.grubcfg = None
    self.grubcfg_lines = None
    self.updated = False
    pass

  def open(self):
    grub_fd = open(self.filename, "r")
    self.grubcfg = grub_fd.read()
    grub_fd.close()

    self.grubcfg_lines = self.grubcfg.splitlines()
    
    for i_line in range(len(self.grubcfg_lines)):
      line = self.grubcfg_lines[i_line][:]
      for variable_name, variable in self.variables.items():
        if variable.parse_line(line, i_line):
          self.override_map[i_line] = variable
          pass
        pass
      pass
    pass

  def set_cmdline_option(self, tag, value):
    for variable_name, variable in self.variables.items():
      variable.set_cmdline_option(tag, value)
      pass
    pass

  def remove_option(self, tag):
    for variable_name, variable in self.variables.items():
      variable.remove_option(tag)
      pass
    pass


  def generate(self) -> typing.Tuple[bool, str]:
    if not self.grubcfg:
      raise Exception("grub_file has not been open.")

    updated = False
    for i_line in range(len(self.grubcfg_lines)):
      override = self.override_map.get(i_line)
      if override:
        original = self.grubcfg_lines[i_line][:]
        generated = override.generate_line()
        if original != generated:
          updated = True
          self.grubcfg_lines[i_line] = generated
          pass
        pass
      pass
    return (updated, "\n".join(self.grubcfg_lines + [""]))
  pass


def grub_set_wce_share(filename = "/etc/default/grub", wce_share="/usr/local/share/wce") -> typing.Tuple[bool, str]:
  grub = grub_config(filename)
  grub.open()
  grub.set_cmdline_option("wce_share", wce_share)
  return grub.generate()


if __name__ == "__main__":
  filename = "/etc/default/grub"
  if len(sys.argv) > 1:
    filename = sys.argv[1]
    pass

  grub = grub_config(filename)
  grub.open()

  grub.set_cmdline_option("wce_share", "/usr/local/share/wce")
  grub.set_cmdline_option("forcepae", None)

  updated, new_grub = grub.generate()
  print( "Updated" if updated else "Unchanged")
  if updated:
    print(new_grub)
    pass

  pass
