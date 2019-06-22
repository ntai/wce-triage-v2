import re, subprocess, os, sys

re_socket_designation = re.compile(r'\s*Socket Designation: ([\w\d]+)')
re_enabled_size = re.compile(r'\s*Enabled Size: (\d+) MB')
re_error_status = re.compile(r'\sError Status: (\w+)')

if __name__ == "__main__":
  sys.path.append(os.path.split(os.getcwd())[0])
  pass

import wce_triage.components.pci as _pci
import wce_triage.components.cpu as _cpu
import wce_triage.components.memory as _memory
import wce_triage.components.network as _network
import wce_triage.components.disk as _disk
import wce_triage.components.video as _video
import wce_triage.components.sound as _sound
import wce_triage.components.optical_drive as _optical_drive

from wce_triage.lib.util import *
from wce_triage.components.disk import Disk, Partition

class Computer:
  def __init__(self):
    self.opticals = []
    self.disks = []
    self.mounted_devices = []
    self.mounted_partitions = []
    self.target = None # Installation destination

    #
    self.decisions = []
    self.decision = None
    pass

  #
  # Find out the mounted partitions
  #
  def detect_mounts(self):
    self.mounted_devices = {}
    self.mounted_partitions = {}

    # Known mounted disks. 
    # These cannot be the target
    mount = subprocess.Popen(["mount"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (mount_out, muont_err) = mount.communicate()
    # Only looking for the device
    mount_re = re.compile(r"(/dev/[a-z]+)([0-9]*) on ([a-z0-9/\.]+) type ([a-z0-9]+) (.*)")
    for line in safe_string(mount_out).splitlines():
      m = mount_re.match(line)
      if m:
        device_name = m.group(1)
        if device_name in self.mounted_devices:
          self.mounted_devices[device_name] = mounted_devices[device_name] + ", " + m.group(3)
        else:
          self.mounted_devices[device_name] = m.group(3)
          pass

        partition_name = m.group(1) + m.group(2)
        self.mounted_partitions[partition_name] = m.group(3)
        pass
      pass

  # list_mounted_disks is true for live-triage
  # list_mounted_disks is false for loading and imaging disk
  def detect_disks(self, list_mounted_disks = True):
    self.disks = []
    self.usb_disks = []

    # Know what's mounted already
    self.detect_mounts()

    # Gather up the possible disks
    possible_disks = find_disk_device_files("/dev/hd") + find_disk_device_files("/dev/sd")
    
    for disk_name in possible_disks:
      # Let's skip the mounted disk
      if disk_name in self.mounted_devices and (not list_mounted_disks):
        # Mounted disk %s is not included in the candidate." % disk_name
        continue

      # Now, I do double check that this is really a disk
      disk = Disk(disk_name)
      if disk.detect_disk():
        if disk.is_usb:
          self.usb_disks.append(disk)
        else:
          self.disks.append(disk)
          pass
        pass
      pass
    pass

  #
  # TRIAGE
  # 

  def gather_info(self):
    self.cpu = _cpu.detect_cpu_type()
    self.memory = _memory.detect_memory()
    self.detect_disks(list_mounted_disks=False)
    #
    self.video = _video.detect_video_cards()
    #
    self.networks = _network.detect_net_devices()
    self.sound_dev = _sound.detect_sound_device()
    pass

  def triage(self, live_system = False):
    self.gather_info();
    self.make_decision()
    return self.decision

  # I guess I could let each module to decide the component triage but
  # spreading it throughout component is a bit too combersome.
  # It's easier to see the oveall decision in one location.
  def make_decision(self):
    #
    cpu = self.cpu
    cpu_detail = "P%d %s %s %dMHz %d cores" % (cpu.cpu_class, cpu.vendor, cpu.model, cpu.speed, cpu.cores)
    self.decisions.append(("CPU", cpu.cpu_class >= 5, cpu_detail))

    # Memory
    ramtype = self.memory.ramtype if self.memory.ramtype is not None else "Unknown"
    self.decisions.append(("Memory", self.memory.total > 2000,  "RAM Type: %s  Size: %dMbytes" % (ramtype, self.memory.total)))

    if len(self.memory.slots) > 0:
      slots = ""
      for slot in self.memory.slots:
        slots = slots + " %s: %d MB%s" % (slot.slot, slot.size, " Installed" if slot.status else "")
        pass
      self.decisions.append(("Memory", True, slots))
      pass
        
    if len(self.disks) == 0:
      self.decisions.append( ("Disk", False, "Hard Drive: NOT DETECTED -- INSTALL A DISK"))
    else:
      msg = "Hard Drive:\n"
      good_disk = False
      for disk in self.disks:
        # print ("%s = %d" % (disk.device_name, disk.get_byte_size()))
        disk_gb = disk.get_byte_size() / 1000000
        disk_msg = "     Device %s: size = %dGbytes  %s" % (disk.device_name, disk_gb, disk.model_name)
        if disk_gb >= 60:
          good_disk = True
          disk_msg += " - Good"
          pass
        else:
          disk_msg += " - TOO SMALL"
          pass
        msg = msg + disk_msg + "\n"
        pass
      self.decisions.append( ( "Disk", good_disk, msg ) )
      pass

    optical_drives = _optical_drive.detect_optical_drives()
    if len(optical_drives) == 0:
      self.decisions.append( ("Optical drive", False, "***** NO OPTICALS: INSTALL OPTICAL DRIVE *****"))
    else:
      msg = "Optical drive:\n"
      index = 1
      for optical in optical_drives:
        msg = msg + "    %d: %s %s %s" % (index, optical.vendor, optical.model_name, optical.get_feature_string(", "))
        index = index + 1
        pass
      self.decisions.append( ("Optical drive", True, msg))
      pass

    blacklist = _pci.detect_blacklist_devices()
    #
    videos = _video.detect_video_cards()

    if len(blacklist.videos) > 0:
      msg = "Remove or disable following video(s) because known to not work\n"
      for video in blacklist.videos:
        msg = msg + "    " + video + "\n"
        pass
      self.decisions.append( ("Video", False, msg))
      pass

    msg = ""
    if videos.nvidia > 0:
      msg = msg + "Video:     nVidia video card = %d\n" % videos.nvidia
      pass
    if videos.ati > 0:
      msg = msg + "Video:     ATI video card = %d\n" % videos.ati
      pass
    if videos.vga > 0:
      msg = msg + "Video:     Video card = %d\n" % videos.vga
      pass

    if (videos.nvidia + videos.ati + videos.vga) >= 0:
      if videos.nvidia > 0:
        self.decisions.append( ("Video", True, "nVidia video card present") )
        pass
      if videos.ati > 0:
        self.decisions.append( ("Video", True, "ATI video card present") )
        pass
      if videos.vga > 0:
        self.decisions.append( ("Video", True, "VGA video card present") )
        pass
      pass

    if len(blacklist.nics) > 0:
      msg = "Remove or disable following cards because known to not work\n"
      for card in blacklist.nics:
        msg = msg + "    " + card + "\n"
        pass
      self.decisions.append( ("Network", False, msg))
      pass

    if len(self.networks) > 0:
      for netdev in self.networks:
        connected = " and connected" if netdev.is_network_connected() else "not connected"
        if netdev.is_wifi():
          msg = "Wifi device '{dev}' detected{conn}. ".format(dev=netdev.device_name, conn=connected)
          pass
        else:
          msg = "Network device '{dev}' detected{conn}".format(dev=netdev.device_name, conn=connected)
        self.decisions.append( ("Network", True, msg))
        pass
      pass
    else:
      msg = "Network device is not present -- INSTALL NETWORK DEVICE"
      self.decisions.append( ("Network", False, msg))
      pass

    if not self.sound_dev:
      self.decisions.append( ("Sound", False, "Sound card: NOT DETECTED -- INSTALL SOUND CARD"))
      pass
    else:
      try:
        subprocess.Popen(["/usr/local/bin/wce-test-sound-device"])
        self.decisions.append( ("Sound", True, "Please connect a speaker. Sound is playing."))
      except:
        self.decisions.append( ("Sound", True, "Sound device is present but music is not playing."))
        pass
      pass

    self.decision = True
    for decision in self.decisions:
      if not decision[1]:
        self.decision = False
        break
      pass
    return
  # End of computer class
  pass


if __name__ == "__main__":
  computer = Computer()
  decision = computer.triage()
  print( "decision %s" % decision)
  for detail in computer.decisions:
    print(detail)
    pass
  pass
