import re, subprocess, os

# PCI vendors
PCI_VENDOR_VIA = "1106"
PCI_VENDOR_SIS = "1039"
PCI_VENDOR_NVIDIA = "10de"
PCI_VENDOR_ATI = "1002"

lspci_nm_re = re.compile(r'\s*([0-9a-f]{2}:[0-9a-f]{2}.[0-9a-f])\s+"([0-9a-f]{2})([0-9a-f]{2})"\s+"([0-9a-f]{4})"\s+"([0-9a-f]{4})"')
lspci_output = None

def get_lspci_nm_output():
  # Dirty trick to avoid running lspci twice...
  global lspci_output
  if not lspci_output:
    lspci = subprocess.Popen("lspci -nm", shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    (lspci_output, err) = lspci.communicate()
    pass
  return lspci_output.decode('utf-8')


# this is partial device class I care
device_classes = {
  '00': 'unclassified', '01': 'mass',     '02': 'network',     '03': 'video',
  '04': 'multimedia',   '05': 'memory',   '06': 'bridge',      '07': 'comm',
  '08': 'peripheral',   '09': 'input',    '0a': 'dock',        '0b': 'processor',
  '0c': 'serialbus',    '0d': 'wireless', '0e': 'intelligent', '0f': 'satellite',
  '10': 'encryption',   '11': 'dsp',      '12': 'cpu-acc',     '13': 'non-essential',
  '40': 'co-proc',      'ff': 'unassigned'
}

def list_pci():
  out = get_lspci_nm_output()
  result = []
  for line in out.splitlines():
    m = lspci_nm_re.match(line)
    # pci-addr device-class vendor device revision subclass? subdevice?
    if m:
      pci_address = m.group(1)
      device_class = device_classes.get(m.group(2))
      device_subclass = m.group(3)
      vendor_id = m.group(4).lower()
      device_id = m.group(5).lower()
      result.append( { "address": pci_address, "class": device_class, "subclass": device_subclass, "vendor": vendor_id, "device": device_id } )
      pass
    pass
  return result


def get_lspci_device_desc(pci_id):
  lspci = subprocess.Popen("lspci -mm -s %s" % pci_id, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
  (out, err) = lspci.communicate()
  lspci_mm_s_re = re.compile(r'\s*([0-9a-f]{2}:[0-9a-f]{2}.[0-9a-f])\s+"([^"]*)"\s+"([^"]*)"\s+"([^"]*)"\s+([^\s]+)\s+"([^"]*)"\s+"([^"]*)"\s*')
  m = lspci_mm_s_re.match(out.encode('utf-8').strip())
  if m:
    return m.group(3) + " " + m.group(4)
  return ""


def safe_read_text(pathname):
  if os.path.exists(pathname):
    filedesc = open(pathname)
    contents = filedesc.read()
    filedesc.close()
    return contents
  return ""

def find_pci_device_node(vendors, devices):
  pci_path = '/sys/bus/pci/devices'
  for a_device in os.listdir(pci_path):
    devnode = os.path.join(pci_path, a_device)
    vendor = safe_read_text(os.path.join(devnode, "vendor"))
    device = safe_read_text(os.path.join(devnode, "device"))
    vendor_id = int(vendor, 16)
    device_id = int(device, 16)
    if vendor_id in vendors and device_id in devices:
      return devnode
    pass
  return None


if __name__ == "__main__":
  for device in list_pci():
    print(str(device))
    pass

  devnode = find_pci_device_node([0x14e4], [0x4312])
  if devnode:
    print('broadcom bcm4312 is found at %s' % devnode)
  else:
    print('broadcom bcm4312 is not found.')
    pass
  pass
  
  
