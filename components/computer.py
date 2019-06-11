import re, subprocess

re_socket_designation = re.compile(r'\s*Socket Designation: ([\w\d]+)')
re_enabled_size = re.compile(r'\s*Enabled Size: (\d+) MB')
re_error_status = re.compile(r'\sError Status: (\w+)')

import components.cpu
import components.memory
import components.network
import components.disk
import components.video
import components.sound
import components.optical_drive

from lib.util import *

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
      # Let's out right skip the mounted disk
      if disk_name in self.mounted_devices and (not list_mounted_disks):
        # Mounted disk %s is not included in the candidate." % disk_name
        continue

      # Now, I do double check that this is really a disk
      disk = components.disk.Disk(disk_name)
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
    self.cpu = components.cpu.detect_cpu_type()
    self.memory = components.memory.detect_memory()
    self.detect_disks(True)
    #
    self.video = components.video.detect_video_cards()
    #
    self.ethernet = components.network.detect_ethernet()
    self.sound_dev = components.sound.detect_sound_device()
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
    cpu_class = self.cpu['class']
    cpu_detail = "P%d %s %s %dMHz %d cores" % (cpu_class, self.cpu['vendor'], self.cpu['model'], self.cpu['speed'], self.cpu['cores'])
    self.decisions.append(("CPU", cpu_class >= 5, cpu_detail))

    if self.memory['ram-type'] == None:
      self.memory['ram-type'] = "Unknown"
      pass

    # Memory
    total_memory = self.memory['total']
    ram_type = self.memory['ram-type']
    rams = self.memory['rams']
    self.decisions.append(("Memory", total_memory > 2000,  "RAM Type: %s  Size: %dMbytes" % (ram_type, total_memory)))

    if len(rams) > 0:
      slots = "    "
      for ram in rams:
        slots = slots + "  %s: %d MB" % (ram[0], ram[1])
        pass
      self.decisions.append(("Memory", True, slots))
      pass
        
    if len(self.disks) == 0:
      self.decisions.append( ("Disk", False, "Hard Drive: NOT DETECTED -- INSTALL A DISK"))
    else:
      msg = "Hard Drive:\n"
      good_disk = False
      for disk in self.disks:
        print ("%s = %d" % (disk.device_name, disk.get_byte_size()))
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

    optical_drives = components.optical_drive.detect_optical_drives()
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

    videos = components.video.detect_video_cards()
    n_nvidia = videos['nvidia']
    n_ati = videos['ati']
    n_vga = videos['vga']
    blacklisted_videos = videos['blacklist']
    msg = ""
    if n_nvidia > 0:
      msg = msg + "Video:     nVidia video card = %d\n" % n_nvidia
      pass
    if n_ati > 0:
      msg = msg + "Video:     ATI video card = %d\n" % n_ati
      pass
    if n_vga > 0:
      msg = msg + "Video:     Video card = %d\n" % n_vga
      pass

    if (n_nvidia + n_ati + n_vga) >= 0:
      if len(blacklisted_videos) > 0:
        msg = "Remove or disable following video(s) because known to not work\n"
        for video in blacklisted_videos:
          msg = msg + "    " + video + "\n"
          pass
        self.decisions.append( ("Video", False, msg))
        pass
      else:
        if n_nvidia > 0:
          self.decisions.append( ("Video", True, "nVidia video card present") )
          pass
        if n_ati > 0:
          self.decisions.append( ("Video", True, "ATI video card present") )
          pass
        if n_vga > 0:
          self.decisions.append( ("Video", True, "VGA video card present") )
          pass
        pass
      pass
    else:
      self.decisions.append( ("Video", False, "No Video card.") )
      pass

    nics = components.network.detect_ethernet()
    eth_devices = nics['devices']
    bad_ethernet_cards = nics['blacklist']

    if len(bad_ethernet_cards) > 0:
      msg = "Remove or disable following cards because known to not work\n"
      for card in bad_ethernet_cards:
        msg = msg + "    " + card + "\n"
        pass
      self.decisions.append( ("Network", False, msg))
      pass

    if len(eth_devices) > 0:
      for eth in eth_devices:
        msg = "Ethernet detected on device {dev}".format(dev=eth.device_name)
        self.decisions.append( ("Network", True, msg))
        pass
      pass
    else:
      msg = "Ethernet card: NOT DETECTED -- INSTALL ETHERNET CARD"
      self.decisions.append( ("Network", False, msg))
      pass

    sound_dev = components.sound.detect_sound_device()
    if not sound_dev:
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
