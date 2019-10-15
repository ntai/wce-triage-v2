#
# GRUB_CMDLINE=""
# GRUB_CMDLINE_LINUX_DEFAULT=""
# export GRUB_CMDLINE_LINUX_DEFAULT_ALT="wce_share=FOO"
#

import re

class kernel_flags:
  tag_value_re = re.compile("(\w[\w_\.]+)=(.+)")

  def __init__(self, cmdline):
    self.values = {}
    self.flags = []
    if cmdline:
      self.set_cmdline(cmdline)
      pass
    pass

  def set_cmdline(self, cmdline):
    for flag in cmdline.split():
      if len(flag) == 0:
        continue
      match2 = self.tag_value_re.match(flag)
      if match2:
        self.flags.append(match2.group(1))
        self.values[match2.group(1)] = match2.group(2)
        pass
      else:
        self.flags.append(flag)
        pass
      pass
    pass


  def set_flag(self, flag):
    if not flag in self.flags:
      self.flags.append(flag)
      pass
    pass

  def set_tag_value(self, tag, value):
    self.set_flag(tag)
    self.values[tag] = value
    pass
  
  def remove_flag(self, flag):
    if flag in self.flags:
      self.flags.remove(flag)
      pass
    if flag in self.values:
      del self.values[flag]
      pass
    pass
  

  def get_cmdline(self):
    return " ".join( [ "%s%s" % (flag, "" if not flag in self.values else ("=%s" % self.values[flag])) for flag in self.flags ] )
  pass
      

if __name__ == "__main__":
  flags = kernel_flags("initrd=wce_amd64/initrd.img hostname=bionic splash nosplash noswap boot=nfs netboot=nfs nfsroot=10.3.2.1:/var/lib/netclient/wcetriage_amd64 acpi_enforce_resources=lax edd=on ip=dhcp nvme_core.default_ps_max_latency_us=0 aufs=tmpfs")

  print(flags.get_cmdline())

  flags.set_flag("forcepae")
  flags.set_tag_value("hostname", "wcex86")
  flags.set_tag_value("nfsroot", "/var/lib/netclinet/wcetriage_x32")
  flags.set_tag_value("nvme_core.default_ps_max_latency_us", "200")
  flags.remove_flag("splash")
  print(flags.get_cmdline())
  pass
