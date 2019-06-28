#
#
#

# Time estimate factors
#
# partition size
# content size
# cpu speed - 
# transport/storage speed
#
# task based correction - some task can report the progress but it's so off.
#
# create - parition, total file size.
#   input - total file size
#   output - compressed image file
#   factors - speed of read
#           - speed of constructing the disk image: cpu seconds it needs per byte/data
#           - speed of compression - cpu seconds it needs per byte
#           - speed of write
#   so the upstream to downstream is defined by
#   (1) input size
#   (2) throughput of input
#   (3) the rate which you can turn input to output - cpu second you need per byte
#   (4) throughput of output
#   the final throughput is decided by the slowest of 3.
#
# what the task can know:
# - the size of input
# - how much cpu time it needs per byte - however this is observed by a reference platform
#
# the downstream speed - for now, the load image is in it's file. However,
# I can write a task to find out the downstream.
#
# The create image task needs multiple factors.
# IOW, task can provide multiple factors, not single factor
#
# Some (most) tasks don't have input (like mount)
# so the time estimate should be dead simple.
# only complex one is partclone. It needs to know the multiple factors, and compute the estiamte from it.
# It should become just a function after declaring the factors.
#
# - declare all the factors.
# - compute.


 
import re



from collections import namedtuple

# TaskNeeds = namedtuple('TaskNeeds', 'source, cpu, transport, fudge')

Multipliers = namedtuple('Multipliers', 'partition, payload, cpu, transport, fudge')
Multipliers.__new__.__defaults__ = (1,)*len(Multipliers._fields)

Evaluators = Multipliers( lambda x, y: x*y,
                          lambda x, y: x*y,
                          lambda x, y: x*y,
                          lambda x, y: min(x, y),
                          lambda x, y: x*y)

class FactorMultiplier(object):
  def __init__(self, name, multipliers=Multipliers()):
    self.name = name
    self.multipliers = multipliers
    pass

  def compute_factors(self, factors):
    return [ Evaluators[i](factor[i], self.multipliers[i]) for i in range(len(self.multipliers)) ]
  pass


class CPUFactor(FactorMultiplier):
  def __init__(self, bogomips, ncore):
    cpuinfo = open('/proc/cpuinfo')
    bogomips = 0
    bogo = re.compile(r'bogomips\s*:\s([\d\.]+)')
    for line in cpuinfo.readlines():
      found = bogo.search(line)
      if found:
        bogomips += float(found.group(1))
        pass
      pass
    super().__init__("cpu", multipliers=Multipliers(cpu=5000/bogomips))
    pass
  pass

  
class PartitionFactor(FactorMultiplier):
  def __init__(self, partition_size_in_MiB):
    super().__init__("partition", multipliers=Multipliers(partition=partition_size_in_MiB/20000))
    pass
  pass

class PayloadFactor(FactorMultiplier):
  def __init__(self, payload_size_in_MiB):
    super().__init__("payload", multipliers=Multipliers(payload=payload_size_in_MiB/10000))
    pass
  pass

# For transport and media speed, whichever slower wins. The media speed is probably
# not linear - like disk read/write speed is faster for outer track. 
# if the file transfer is over network, that should be added as well.
#
# For the I/O speed, the estimate speed needs to come from outside of
# this module.
# For the unknown storage, generic estimate needs to happen.
transport_estimate = { "e10" : 1,
                       "e100": 7,
                       "e1000": 60,
                       "usb1": 1,
                       "usb2": 15,
                       "usb3": 100,
                       "ata": 60,
                       "sata": 120};

class TransportFactor(FactorMultiplier):
  def __init__(self, xfer_speed):
    self.xfer_speed = xfer_speed
    super().__init__("transport", multipliers=Multipliers(transport=xfer_speed))
    pass
  pass

