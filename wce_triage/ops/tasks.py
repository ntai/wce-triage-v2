#
# Tasks: each task is a operation. Some tasks can take a long time.
#
# For example, a task is like mkfs. As the task runs, it should produce progress
#
# By calling into diskop, it creates the plan - which is the sequence of tasks.
# exec runs through the tasks.
#

import datetime, re, subprocess, abc, os, select, time
import components.pci

class op_task(object, metaclass=abc.ABCMeta):
  def __init__(self, description):
    self.description = description
    self.is_started = False
    self.is_done = False
    self.progress = 0
    self.message = None # Progress message
    self.start_time = None
    self.end_time = None
    pass

  @abc.abstractmethod
  def start(self):
    pass

  @abc.abstractmethod
  def poll(self):
    pass

  @property
  def get_description(self):
    return self.description
  
  def set_progress(self, progress, msg):
    self.progress = progress
    self.message = msg
    pass

  def _noop(self):
    self.is_started = True
    self.is_done = True
    self.progress = 100
    self.start_time = datetime.datetime.now()
    self.end_time = self.start_time
    pass

  pass


# Base class for Python based task
class op_task_python(op_task):
  def __init__(self, description):
    super().__init__(description)
    pass

  def start(self):
    self.start_time = datetime.datetime.now()
    pass
  
  def poll(self):
    self.run_python()
    self.end_time = datetime.datetime.now()
    pass

  @abc.abstractmethod
  def run_python(self):
    pass

  pass


# Base class for subprocess based task
class op_task_process(op_task):
  def __init__(self, description, argv=None, part=None, select_timeout=1):
    super().__init__(description)

    self.argv = argv
    self.partition = part
    self.process = None
    self.select_timeout = select_timeout
    pass

  def start(self):
    self.start_time = datetime.datetime.now()
    self.process = subprocess.Popen(self.argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self.stdout = self.process.stdout
    self.stderr = self.process.stderr
    self.read_set = [self.stdout, self.stderr]
    self.out = ""
    self.err = ""
    pass

  def _poll_process(self):
    selecting = True
    while selecting:
      selecting = False
      try:
        rlist, wlist, xlist = select.select(self.read_set, [], [], self.select_timeout)
      except select.error as e:
        if e.args[0] == errno.EINTR:
          selecting = True
          pass
        raise
      pass
      
    if self.stdout in rlist:
      data = os.read(self.stdout.fileno(), 1024)
      if data == "":
        self.read_set.remove(self.stdout)
        pass
      else:
        self.out = self.out + data.decode('utf-8')
        pass
      pass

    if self.process.returncode is not None:
      self.end_time = datetime.datetime.now()
      pass

    pass

  def _update_progress(self):
    if self.process.returncode is None:
      # Let's fake it.
      wallclock = datetime.datetime.now()
      dt = wallclock - self.start_time
      progress = self._estimate_progress(dt.total_seconds())
      if progress > 99:
        self.set_progress(999, "timed out")
      else:
        self.set_progress(progress, "running" )
        pass
      pass
    elif self.process.returncode in self.good_returncode:
      self.set_progress(100, "finished" )
    else:
      self.set_progress(999, "failed with return code %d" % self.process.returncode)
      pass
    pass

  def _estimate_progress(self, total_seconds):
    return int(total_seconds * 5)

  def poll(self):
    self._poll_process()
    self._update_progress()
    pass

  pass


#
# mkdir uses Python os.mkdir
#
class task_mkdir(op_task_python):

  def __init__(self, description, dir_path):
    '''
    :param op: diskop instance
    :param description: description of operation
    :param dir_path: path to do mkdir

    '''
    super().__init__(description)
    self.dir_path = dir_path
    pass

  def run_python(self):
    if not os.path.exist(self.dir_path):
      try:
        os.mkdir(self.dir_path)
        self.is_done = True
        self.progress = 100
        pass
      except Exception as exc:
        self.is_done = True
        self.progress = 999
        pass
      pass
    else:
      self.is_done = True
      self.progress = 100
      pass
    pass

  pass


#
#
class task_partclone(op_task_process):

  def __init__(self, description):
    super().__init__(description)

    self.start_re = []
    self.start_re.append(re.compile(r'Partclone [^ ]+ http://partclone.org\n'))
    self.start_re.append(re.compile(r'Starting to clone device \(/dev/\w+\) to image \([^\)]+\)\n'))
    self.start_re.append(re.compile(r'Reading Super Block\n'))
    self.start_re.append(re.compile(r'Calculating bitmap... Please wait... [^\n]+\n[^\n]+\n[^\n]+\n'))
    self.start_re.append(re.compile(r'File system:\s+EXTFS\n'))
    self.start_re.append(re.compile(r'Device size:\s+[\d.]+\s+GB\n'))
    self.start_re.append(re.compile(r'Space in use:\s+[\d.]+\s+GB\n'))
    self.start_re.append(re.compile(r'Free Space:\s+[\d.]+\s+MB\n'))
    self.start_re.append(re.compile(r'Block size:\s+\d+\s+Byte\n'))
    self.start_re.append(re.compile(r'Used block :\s+\d+\n'))
    
    self.progress_re = re.compile(r'\r\s+\rElapsed: (\d\d:\d\d:\d\d), Remaining: (\d\d:\d\d:\d\d), Completed:\s+(\d+.\d*)%,\s+([^\/]+)/min,')
    pass

  def poll(self):
    #
    # This drives/fetches the process output
    self._poll_process()

    # Check the progress
    if len(self.err) > 0:
      while len(self.start_re) > 0:
        m = self.start_re[0].match(self.err)
        if not m:
          break
        start_re = self.start_re[1:]
        self.err = self.err[len(m.group(0)):]
        pass
      if len(start_re) == 0:
        self.set_progress(10, "Start imaging")
      else:
        while True:
          m = self.progress_re.search(self.err)
          if not m:
            break
          self.err = self.err[len(m.group(0)):]

          elapsed = m.group(1)
          remaining = m.group(2)
          completed = float(m.group(3))

          self.set_progress(round(completed*0.9)+10, "elapsed: %s remaining: %s" % (elapsed, remaining))
          pass
        pass
      pass
    
    if self.process.returncode is not None:      
      if self.process.returncode == 0:
        self.set_progress(100, "Success")
      else:
        self.set_progress(999, "Failed")
        pass
      pass
    pass
  pass

#
#
#
class task_mkfs(op_task_process):
  def __init__(self, description, partition=None):
    super().__init__(self, description)
    self.success_returncodes = [0]
    self.success_msg = "Initializing file system succeeded."
    self.failure_msg = "Initializing file system failed."
    self.part = partition
    pass

  def start(self):

    if self.part.partition_type == 'c':
      self.argv = ["mkfs.vfat", "-F", "32", "-n", name, part.device_name]
      self.description = "Creating vfat partition"
    elif part.partition_type == '83':
      # I got the list from the ext4 standard installation with Ubuntu 18.04
      fs_features = 'has_journal,ext_attr,resize_inode,dir_index,filetype,needs_recovery,extent,64bit,flex_bg,sparse_super,large_file,huge_file,dir_nlink,extra_isize,metadata_csum'
      self.argv = ["mkfs.ext4", "-O", fs_features, "-L", self.part.partition_name, "-U", self.part.partition_uuid, self.part.device_name]
    else:
      raise Exception("Unsuppoted partition type")

    super().start()
    pass
    
  #
  def _estimate_progress(self, total_seconds):
    return int(total_seconds) / 5

  pass

#
#
#
class task_unmount(op_task_process):
  def __init__(self, description, partition=None, force_unmount=False):
    super().__init__(description)
    self.part = partition
    self.force = force_unmount
    pass
  
  def start(self):
    if not self.force and not self.part.mounted:
      return
    cmd = ["/bin/umount"]
    if force:
      cmd.append("-f")
      pass
    cmd.append(part.device_name)

    super().start()
    pass

  def _estimate_progress(self, total_seconds):
    return int(total_seconds * 10)

  pass


class task_mount(op_task_process):

  def __init__(self, description, partition=None):
    super().__init__(description)
    self.part = partition
    pass
  

  def start(self):
    mount_point = self.part.get_mount_point()
    if not os.path.exists(mount_point):
      raise Exception("No mount point")
      pass
    self.argv = ["/bin/mount", self.part.device_name, mount_point]
    super().start()
    pass

  def _estimate_progress(self, total_seconds):
    return int(total_seconds * 10)

  pass


class task_assign_uuid_to_partition(op_task_process):

  def __init__(self, description, disk=None, partition_id=None):
    super().__init__(description)
    self.disk = disk
    self.part_id = partition_id
    pass
  

  def start(self):
    self.part = self.disk.find_partition(self.part_id)
    if self.part is None:
      self.set_progress(999, "Partition %s on disk %d is not found." % (self.part_id, self.disk.device_name))
      return

    if self.part.partition_type == "83":
      self.argv = ["tune2fs", "%s1" % part.device_name, "-U", part.partition_uuid, "-L", "/"]
    elif part.partition_type == "C":
      self.argv = ["mkswap", "-U", disk.uuid2, "%s5" % disk.device_name]
      pass
    else:
      raise Exception("unsupported partition type")
    super().start()
    pass

  def _estimate_progress(self, total_seconds):
    return int(total_seconds * 0.2)

  pass


class task_install_bootloader(op_task_process):

  def __init__(self, description, disk=None):
    super().__init__(description)
    self.disk = disk
    pass

  def start(self):
    self.argv = ["/usr/bin/syslinux", "-maf", self.disk.device_name]
    super().start()
    pass

  def _estimate_progress(self, total_seconds):
    return int(total_seconds * 10)

  pass


def task_get_uuid_from_partition(op_task_process):
  def __init__(self, description, partition=None):
    super().__init__(description)

    self.part = partition
    pass

  def start(self):
    self.part.partition_uuid = None
    self.argv = ["/sbin/blkid", part.device_name]
    pass

  def _estimate_progress(self, total_seconds):
    return int(total_seconds * 10)


  def poll(self):
    super().poll()

    if self.progress == 100:
      blkid_re = re.compile(r'/dev/(\w+)1: LABEL="([/\w\.\d]+)" UUID="([\w\d]+-[\w\d]+-[\w\d]+-[\w\d]+-[\w\d]+)" TYPE="([\w\d]+)"')
      for line in safe_string(self.out).splitlines():
        m = blkid_re.match(line)
        if m:
          self.part.partition_uuid = m.group(2)
          break
      pass
    pass
  pass


class task_restore_disk_image(task_partclone):
  
  # Restore partclone image file to the first partition
  def __init__(self, description, disk=None, partition_id=None, source=None):
    super().__init__(description)
    self.disk = disk
    self.part_id = partition_id
    self.source = source
    pass

  def start(self):
    part1 = self.disk.find_partition(self.part_id)

    if part1 is None:
      # Partition is not there.
      self.set_progress(999, "Partition %s does not exist on %s" % (self.part_id, self.disk.device_name))
      return

    decomp = get_file_decompression_app(self.source)
    transport_scheme = get_transport_scheme(self.source)

    if transport_scheme:
      self.argv = "wget -q -O - '%s' | %s | partclone.ext4 -r -s - -o %s" % (self.source, decomp, part1.device_name)
    else:
      if decomp == "cat":
        self.argv = "partclone.ext4 -r -s %s -o %s" % (self.source, part1.device_name)
      else:
        self.argv = "%s '%s' | partclone.ext4 -r -s - -o %s" % (decomp, self.source, part1.device_name)
        pass
      pass
    self.set_progress(0, "Restore disk image")
    pass

  pass


class task_fsck(op_task_process):
  #
  def __init__(self, description, disk=None, partition_id=None):
    self.disk = disk
    self.part_id = partition_id
    pass

  def start(self):
    #
    part1 = self.disk.find_partition(self.part_id)
    self.argv = ["/sbin/e2fsck", "-f", "-y", part1.device_name]
    pass
   
  pass


class task_expand_partition(op_task_process):
  #
  def __init__(self, description, disk=None, partition_id=None):
    super().__init__(description)
    self.disk = disk
    self.part_id = partition_id
    pass

  def start(self):
    #
    part1 = self.disk.find_partition(self.part_id)
    if part1 is None:
      self.set_progress(999, "Partition %s does not exist on %s" % (self.part_id, self.disk.device_name))
      return

    self.argv = ["resize2fs", "-p", (part1.device_name)]
    super().start()
    return

  pass


class task_shrink_partition(op_task_process):
  #
  def __init__(self, description, disk=None, partition_id=None):
    super().__init__(description)
    self.disk = disk
    self.part_id = partition_id
    pass

  def start(self):
    #
    part1 = self.disk.find_partition(self.part_id)
    if part1 is None:
      self.set_progress(999, "Partition %s does not exist on %s" % (self.part_id, self.disk.device_name))
      return

    self.argv = ["resize2fs", "-M", (part1.device_name)]
    super().start()
    return

  def _estimate_progress(self, total_seconds):
    return int(total_seconds * 0.2)

  pass


class task_finalize_disk(op_task_process):
  def __init__(self, description, disk=None):
    super().__init__(description)
    self.disk = disk
    pass

  def start(self):
    self.argv = ["blkid"]
    pass

  def poll(self):
    super().poll()
    
    if self.progress == 100:
      this_disk = re.compile(r'(' + self.disk.device_name + r'\d): ((LABEL=\"[^"]+\") ){0,1}(UUID=\"([0-9a-f-]+)\")\s+TYPE=\"([a-z0-9]+)\"')
      for line in self.out.splitlines():
        m = this_disk.match(line)
        if m:
          if m.group(6) == "swap":
            self.uuid2 = m.group(5)
          elif  m.group(6)[0:3] == "ext":
            self.uuid1 = m.group(5)
            pass
          pass
        pass
    
      # print("# Primary %s1 - UUID: %s" % (self.device_name, self.uuid1))
      # print("# Swap    %s5 - UUID: %s" % (self.device_name, self.uuid2))
      pass
    pass
  pass


class task_create_wce_tag(op_task_python):
  def __init__(self, description, disk=None, source=None):
    super().__init__(description)
    self.disk = disk
    self.source = source
    pass
  
  def start(self):
    # Set up the /etc/wce-release file
    release = open(self.disk.wce_release_file, "w+")
    release.write("wce-contents: %s\n" % get_filename_stem(self.source))
    release.write("installer-version: %s\n" % installer_version)
    release.write("installation-date: %s\n" % datetime.datetime.isoformat( datetime.datetime.utcnow() ))
    release.close()
    self.set_progress(100, "WCE release tag written")
    pass
  
  pass


class task_create_image_disk(op_task_process):
  
  def __init__(self, description, disk=None, partition_id=None, stem_name=None):
    super().__init__(description)
    self.stem_name = stem_name
    self.disk = disk
    self.part_id = partition_id
    pass

  def start(self):
    self.start_time = datetime.datetime.now()

    if not os.path.exists("/mnt/www/wce-disk-images"):
      return

    imagename = "/mnt/www/wce-disk-images/%s-%s.partclone.gz" % (self.stem_name, datetime.date.today().isoformat())

    part1 = self.disk.find_partition(self.part_id)
    
    if comp == "cat":
      self.argv = ["/usr/sbin/partclone.extfs", "-B", "-c" "-s", part1.device_name, "-o", imagename]
    else:
      self.argv = ["/usr/sbin/partclone.extfs", "-B", "-c", "-s", part1.device_name, "-o", "-" ]
      pass

    self.process = subprocess.Popen(self.argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if comp != "cat":
      outputfile = open(imagename, "w")
      errorfile = open("/tmp/comp-error", "w")
      self.argv2 = [comp]
      self.process2 = subprocess.Popen(self.argv2, stdin=self.process.stdout, stdout=outputfile, stderr=errorfile)
      pass
    pass
  
  pass

# This is to purge the persistent rules for network and cd devices so that the clone
# installation will have correct device names
class task_remove_persistent_rules(op_task_python):
    #
  def __init__(self, description, disk=None):
    super().__init__(description)
    self.disk = disk
    pass

  def start(self):
    files = ["/etc/wce-release",
             "/var/lib/world-computer-exchange/access-timestamp",
             "/var/lib/world-computer-exchange/computer-uuid",
             "/etc/udev/rules.d/70-persistent-cd.rules",
             "/etc/udev/rules.d/70-persistent-net.rules"]
    n = len(files)
    i = 0
    for path in files:
      i = i + 1
      if os.path.exists(path):
        try:
          os.remove(path)
        except:
          pass
        pass
      self.set_progress(100.0 * i / n, "Removing file %s" % path)
      pass

    self.set_progress(100, "Persistent rules removed.")
    pass
  pass


class task_install_mbr(op_task_process):
  def __init__(self, description, disk=None):
    super().__init__(description)
    self.disk = disk
    pass

  def start(self):
    self.argv = ["/sbin/install-mbr", "-f", "-r", self.disk.device_name]
    super().start()
    pass
  
  pass


class task_get_disk_geometry(op_task_process):
  def __init__(self, disk, memsize, verbose):
    pass

  def start(self):
    self.argv = "parted -s -m %s unit s print" % (self.device_name)
    super().start()
    pass

  def poll(self):
    super().poll()
    
    if self.progress >= 100:
      if self.process.returncode == 0:
        lines = self.out.split("\n")
        disk_line = lines[1]
        columns = disk_line.split(":")
        if columns[0] != self.disk.device_name:
          sys.exit(1)
          pass
        sectors = int(columns[1][:-1])
        self.disk.sectors = sectors
        pass
      pass
    pass
  pass


class task_partition_disk(op_task_process):
  def __init__(self, description, disk=None, memsize=None):
    super().__init__(description)
    self.disk = disk
    self.memsize = memsize
    pass

  def start(self):
    # Everything is multiple of 8, so that 4k sector problem never happens
    sectors = (self.disk.sectors / 8) * 8
    
    max_swap_sectors = 3 * (((memsize * 1024) / 512) * 1024)
    min_swap_sectors = (((memsize * 1024) / 512) * 1024) / 2
    swap_sectors = sectors / 20
    if swap_sectors > max_swap_sectors:
      swap_sectors = max_swap_sectors
      pass
    
    if swap_sectors < min_swap_sectors:
      swap_sectors = min_swap_sectors
      pass
    
    part1_start = 2048
    part2_start = ((sectors - part1_start - swap_sectors - 8) / 8) * 8
    part5_start = part2_start + 8
    part1_end = part2_start - 1
    part2_end = sectors - 1 
    part5_end = part2_end
    
    self.args = ["parted", "-s", self.device_name, "unit", "s", "mklabel", "msdos", "mkpart", "primary", "ext2", "2048", "%d" % part1_end, "mkpart", "extended", "%d" % part2_start, "%d" % part2_end, "mkpart", "logical", "linux-swap", "%d" % part5_start, "%d" % part5_end, "set", "1", "boot", "on" ]

    super().start()
    pass

  pass
  
class task_create_partitions_for_usb_stick():

  def __init__(self, description, disk=None):
    super().__init__(description)
    self.disk = disk
    pass

  def start(self):
    byte_size = self.disk.get_byte_size()
    sectors = byte_size / 512
    part1_sectors = (750 * 1024 * 1024) / 512
    part1_start = 2048
    if part1_sectors + part1_start > (sectors / 2):
      part1_sectors = (sectors / 2) - part1_start
      pass
    part1_end = part1_start + part1_sectors - 1
    part2_start = part1_start + part1_sectors
    part2_end = sectors - 1 
    # print("# %s byte size %d sectors %d part1_sectors %d" % (self.device_name, byte_size, sectors, part1_sectors))
    
    self.argv = ["parted", "-s", self.device_name, "unit", "s", "mklabel", "msdos", "mkpart", "primary", "fat32", "%d" % part1_start, "%d" % part1_end, "mkpart", "primary", "ext2", "%d" % part2_start, "%d" % part2_end, "set", "1", "boot", "on" ]

    super().start()
    pass

  pass
  

class task_refresh_partition(op_task_process):
  def __init__(self, description, disk=None):
    super().__init__(description)
    self.disk = disk
    pass
  
  def start(self):
    self.argv = ["fdisk", "-l", "-u", self.disk.device_name]
    super().start()
    pass
  
  def poll(self):
    super().poll()

    if self.progress == 100:
      self.disk.partitions = []
    
      looking_for_partition = False

      for line in self.out.splitlines():
        if looking_for_partition:
          m = part_re.match(line)
          if m:
            self.partitions.append(Partition(device_name = m.group(1),
                                             partition_type = m.group(2)))
            pass
          pass
        else:
          if line == "":
            looking_for_partition = True
            continue
          pass
        pass
      pass
    pass
  pass

    
class task_install_grub():

  def __init__(self, description, mount_dir, detected_video):
    self.mount_dir = mount_dir
    self.script = [
      "#!/bin/sh",
      "mount -t proc none /proc",
      "mount -t sysfs none /sys",
      "mount -t devpts none /dev/pts",
      "#"]
    (self.n_nvidia, self.n_ati, self.n_vga, self.n_black_vga, self.blacklisted_videos) = detected_video
    pass


  def start(self):
    part1 = self.disk.find_partition(1)
    script_path_template = "%s/tmp/install-grub"
    script_path = script_path_template % self.mount_dir

    # Things to do is installing grub
    self.script.append("/usr/sbin/grub-install %s" % self.disk.device_name)
    self.script.append("N_NVIDIA=%d" % self.n_nvidia)
    self.script.append("N_ATI=%d" % self.n_ati)
    self.script.append("N_VGA=%d" % self.n_vga)
        
    self.script.append("if [ $N_ATI .gt. 0  || $N_VGA .gt. > 0]; then")
    self.script.append("  apt-get -q -y --force-yes purge `dpkg --get-selections | cut -f 1 | grep -v xorg | grep nvidia-`")
    self.script.append("fi")

    # 
    self.script.append('#')
    self.script.append('chmod +rw /boot/grub/grub.cfg')
    self.script.append('export GRUB_DEVICE_UUID="%s"' % part1.uuid)
    self.script.append('export GRUB_DISABLE_OS_PROBER=true')
    self.script.append('export GRUB_DISABLE_LINUX_UUID=false')
    self.script.append('grub-mkconfig -o /boot/grub/grub.cfg')

    self.script.append('#')
    self.script.append('cp /boot/grub/grub.cfg /tmp/grub.cfg')
    self.script.append(r"sed \"s/root='(hd.,1)'/root='(hd0,1)'/g\" /tmp/grub.cfg > /boot/grub/grub.cfg")

    self.script.append('#')
    self.script.append('chmod 444 /boot/grub/grub.cfg')
    self.script.append('umount /proc || umount -lf /proc')
    self.script.append('umount /sys')
    self.script.append('umount /dev/pts')
    self.script.append('# script end')

    script_file = open(script_path, "w")
    script_file.write("\n".join(self.script))
    script_file.close()
    
    subprocess.call("mount --bind /dev/ %s/dev" % self.mount_dir, shell=True)
    os.chmod(script_file_path % self.mount_dir, 0o755)
    self.argv = ["/usr/sbin/chroot", self.mount_dir, "/bin/sh", script_path_template % ""]
    super().start()
    pass

  def poll(self):
    super().poll()
  
    if self.progress >= 100:
      subprocess.call("umount %s/dev" % self.mount_dir, shell=True)
      pass

    pass
  pass



fstab_template = '''# /etc/fstab: static file system information.
#
# Use 'blkid -o value -s UUID' to print the universally unique identifier
# for a device; this may be used with UUID= as a more robust way to name
# devices that works even if disks are added and removed. See fstab(5).
#
# <file system> <mount point>   <type>  <options>       <dump>  <pass>
proc            /proc           proc    nodev,noexec,nosuid 0       0
# / was on /dev/sda1 during installation
UUID=%s /               ext4    errors=remount-ro 0       1
# swap was on /dev/sda5 during installation
UUID=%s none            swap    sw              0       0
'''

class task_finalize_disk(op_task_python):
  def __init__(self, description, disk=None, mount_dir=None, newhostname=None):
    super().__init__(description)
    self.mount_dir = mount_dir
    self.disk = disk
    self.newhostname = newhostname
    pass
   
  def run_python(self):
    # patch up the restore
    part1 = self.disk.find_partition(1)
    part2 = self.disk.find_partition(5)
    fstab = open("%s/etc/fstab" % self.mount_dir, "w")
    fstab.write(fstab_template % (part1.uuid, part2.uuid))
    fstab.close()

    #
    # New hostname
    #
    if self.newhostname:
      # Set up the /etc/hostname
      etc_hostname_filename = "%s/etc/hostname" % self.mount_dir
      hostname_file = open(etc_hostname_filename, "w")
      hostname_file.write("%s\n" % newhostname)
      hostname_file.close()

      # Set up the /etc/hosts file
      etc_hosts_filename = "%s/etc/hosts" % self.mount_dir
      hosts = open(etc_hosts_filename, "r")
      lines = hosts.readlines()
      hosts.close()
      hosts = open(etc_hosts_filename, "w")

      this_host = re.compile(r"127\.0\.1\.1\s+[a-z_A-Z0-9]+\n")
      for line in lines:
        m = this_host.match(line)
        if m:
          hosts.write("127.0.1.1\t%s\n" % newhostname)
        else:
          hosts.write(line)
          pass
        pass
      hosts.close()
      pass


    #
    # Remove the WCE follow up files
    # 
    for removing in ["%s/var/lib/world-computer-exchange/computer-uuid",
                     "%s/var/lib/world-computer-exchange/access-timestamp"]:
      try:
        os.unlink( removing % self.mount_dir)
      except:
        pass
      pass

    #
    # Patch up the grub.cfg just in case the "/dev/disk/by-uuid/%s" % 
    # self.uuid1 does not exist. If that happens, grub-mkconfig 
    # genertes the device name based grub.cfg which is bad.
    #
    # This should fix up the most of unbootable disk imaging.
    #
    root_fs = "UUID=%s" % part1.uuid
    linux_re = re.compile(r'(\s+linux\s+[^ ]+\s+root=)([^ ]+)(\s+ro .*)')
    grub_cfg_file = open("%s/boot/grub/grub.cfg" % self.mount_dir)
    grub_cfg = grub_cfg_file.readlines()
    grub_cfg_file.close()
    grub_cfg_file = open("%s/boot/grub/grub.cfg" % self.mount_dir, "w")
    for line in grub_cfg:
      m = linux_re.match(line)
      if m:
        grub_cfg_file.write("%s%s%s\n" % (m.group(1), root_fs, m.group(3)))
      else:
        grub_cfg_file.write(line)
        pass
      pass
    grub_cfg_file.close()
    pass
  pass


class task_mount_nfs_destination(op_task_process):

  def __init__(self, description):
    pass
  
  def start(self):
    if not is_network_connected():
      self.set_progress(999, "Network is not working.")
      return
    
    if nfs_server is None:
      nfs_server = get_router_ip_address()
      pass

    if not nfs_server:
      self.set_progress(999, "No NFS server")
      return

    # Mount the NFS to /mnt/www
    if not os.path.exists("/mnt/www"):
      try:
        os.mkdir("/mnt/www")
      except:
        self.set_progress(999, "Failed to mkdir mount point.")
        pass
      pass

    self.argv = [ "mount", "-t", "nfs",  "%s:/var/www" %nfs_server, "/mnt/www"]
    super().start()
    pass
  pass

#
# Sleep task - for testing
#
class task_sleep(op_task_process):
  def __init__(self, description, duration):
    super().__init__(description)
    self.duration = duration
    self.argv = ['sleep', str(duration)]
    pass

  def _estimate_progress(self, total_seconds):
    wallclock = datetime.datetime.now()
    dt = wallclock - self.start_time
    return 100 * (dt.total_seconds()/self.duration)
  pass


# Package uninsall base class
class task_uninstall_package(disk_op_task_process):

  def __init__(self, op, description, packages=None):
    super().__init__(op, description)
    self.packages = packages
    pass
  
  def start(self):
    if self.packages:
      self.argv = [ "apt", "purge", "-y" ] + self.packages
      super().start()
      pass
    pass

  pass

#
# Uninstall Broadcom STA
#
class task_uninstall_bcmwl(task_uninstall_package):
  
  def __init__(self, op, description, packages=None):
    super().__init__(op, description)
    pass
  
  def start(self):
    if components.pci.find_pci_device_node([0x14e4], [0x4312]):
      self.packages = ['bcmwl-kernel-source']
      super().start()
      pass
    else:
      self._noop()
      pass
    pass
  pass


#
if __name__ == "__main__":
  task = task_sleep('test', 5)
  task.start()
  
  while task.progress < 99:
    task.poll()
    print("FOO")
    pass
  print('done')
  pass

