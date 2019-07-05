#!/usr/bin/env python3

from wce_triage.components import pci as _pci
from wce_triage.components import cpu as _cpu
from wce_triage.components import memory as _memory
from wce_triage.components import network as _network
from wce_triage.components import disk as _disk
from wce_triage.components import video as _video
from wce_triage.components import sound as _sound
from wce_triage.components import optical_drive as _optical_drive

import re, subprocess, os, sys, json

re_socket_designation = re.compile(r'\s*Socket Designation: ([\w\d]+)')
re_enabled_size = re.compile(r'\s*Enabled Size: (\d+) MB')
re_error_status = re.compile(r'\sError Status: (\w+)')


from wce_triage.lib.util import *
#from wce_triage.lib.hwinfo import *
from wce_triage.components.disk import Disk, Partition

tlog = get_triage_logger()


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
        self.disks.append(disk)
        pass
      pass
    pass

  #
  # TRIAGE
  # 

  def gather_info(self):
    #self.hw_info = hw_info()
    self.hw_info = None

    self.cpu = _cpu.detect_cpu_type(self.hw_info)
    self.memory = _memory.detect_memory(self.hw_info)
    self.detect_disks(list_mounted_disks=False)
    #
    self.video = _video.detect_video_cards(self.hw_info)
    #
    self.networks = _network.detect_net_devices(self.hw_info)
    self.sound_dev = _sound.detect_sound_device(self.hw_info)
    pass

  # lshw is far better!
  def _run_lshw(self):
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
    self.decisions.append( {"component": "CPU",
                            "result":  cpu.cpu_class >= 5,
                            "message": cpu_detail,
                            "details": cpu_detail } )

    # Memory
    ramtype = self.memory.ramtype if self.memory.ramtype is not None else "Unknown"
    mem_info = "RAM Type: %s  Size: %dMbytes" % (ramtype, self.memory.total)
    self.decisions.append( {"component": "Memory",
                            "message": mem_info,
                            "result": self.memory.total > 2000,
                            "details": mem_info})

    if len(self.memory.slots) > 0:
      slots = ""
      for slot in self.memory.slots:
        slots = slots + " %s: %d MB%s" % (slot.slot, slot.size, " Installed" if slot.status else "")
        pass
      self.decisions.append({"component": "Memory",
                             "result": True,
                             "message": slots,
                             "details": slots})
      pass
        
    if len(self.disks) == 0:
      self.decisions.append( {"component": "Disk", "result": False, "message": "Hard Drive: NOT DETECTED -- INSTALL A DISK"})
    else:
      for disk in self.disks:
        if disk.mounted:
          continue
        msg = ""
        good_disk = False
        tlog.debug("%s = %d" % (disk.device_name, disk.get_byte_size()))
        disk_gb = disk.get_byte_size() / 1000000000
        disk_msg = "     Device %s: size = %dGbytes  %s" % (disk.device_name, disk_gb, disk.model_name)
        if disk_gb >= 60:
          good_disk = True
          disk_msg += " - Good"
          pass
        else:
          disk_msg += " - TOO SMALL"
          pass
        msg = msg + disk_msg 

        self.decisions.append( {"component": "Disk",
                                "result": good_disk,
                                "device": disk.device_name,
                                "message": msg,
                                "details": msg })
        pass
      pass

    optical_drives = _optical_drive.detect_optical_drives(self.hw_info)
    if len(optical_drives) == 0:
      self.decisions.append( { "component": "Optical drive",
                               "result": False,
                               "message": "***** NO OPTICALS: INSTALL OPTICAL DRIVE *****" })
    else:
      msg = ""
      index = 1
      for optical in optical_drives:
        msg = msg + " %d: %s %s %s" % (index, optical.vendor, optical.model_name, optical.get_feature_string(", "))
        self.decisions.append( {"component": "Optical drive",
                                "result": False,
                                "device": optical.device_name,
                                "message": msg,
                                "details": msg })
        index = index + 1
      pass

    blacklist = _pci.detect_blacklist_devices()
    #
    videos = _video.detect_video_cards(self.hw_info)

    if len(blacklist.videos) > 0:
      msg = "Remove or disable following video(s) because known to not work\n"
      for video in blacklist.videos:
        msg = msg + "  " + video + "\n"
        pass
      self.decisions.append( {"component": "Video", "result": False, "message": msg})
      pass

    #
    if (videos.nvidia + videos.ati + videos.vga) >= 0:
      if videos.nvidia > 0:
        self.decisions.append( {"component": "Video", "result": True, "message": "nVidia video card present" } )
        pass
      if videos.ati > 0:
        self.decisions.append( {"component": "Video", "result": True, "message": "ATI video card present" } )
        pass
      if videos.vga > 0:
        self.decisions.append( {"component": "Video", "result": True, "message": "VGA video card present" } )
        pass
      pass

    if len(blacklist.nics) > 0:
      msg = "Remove or disable following cards because known to not work\n"
      for card in blacklist.nics:
        msg = msg + "  " + card + "\n"
        pass
      self.decisions.append( {"component": "Network", "result": False, "message": msg } )
      pass

    if len(self.networks) > 0:
      for netdev in self.networks:
        connected = " and connected" if netdev.is_network_connected() else " not connected"
        if netdev.is_wifi():
          msg = "WIFI device '{dev}' detected{conn}. ".format(dev=netdev.device_name, conn=connected)
          pass
        else:
          msg = "Network device '{dev}' detected{conn}".format(dev=netdev.device_name, conn=connected)
          pass
        self.decisions.append( {"component": "Network",
                                "device": netdev.device_name,
                                "device_type": netdev.get_device_type_name(),
                                "result": netdev.is_network_connected(),
                                "message": msg } )
        pass
      pass
    else:
      msg = "Network device is not present -- INSTALL NETWORK DEVICE"
      self.decisions.append( { "component": "Network",
                               "result": False,
                               "message": msg })
      pass

    if not self.sound_dev:
      self.decisions.append( {"component": "Sound",
                              "result": False,
                              "message": "Sound card: NOT DETECTED -- INSTALL SOUND CARD"})
      pass
    else:
      self.decisions.append( {"component": "Sound",
                              "result": False,
                              "message": "Sound card detected -- Hit [play] button"})
      pass

    self.decision = True
    for decision in self.decisions:
      if not decision.get("result"):
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
