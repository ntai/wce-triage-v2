#
#
#
import os, sys
import logging
tlog = logging.getLogger('triage')

MiB = 2**20

#   (0) input size
#   (1) my own througput limit - like the bandwidth
#   (2) throughput of input
#   (3) conversion from input to output
#   (4) cpu second you need per input throughput
#   optional fixed overhead - somethings just need a bit of time
#
# -- result how much total time this one needs 
#
class DataPath:
  def __init__(self, name, rate_limit=None, io_ratio=1, cpu_second=0, fixed_overhead=0):
    self.name = name
    self.rate_limit = rate_limit # my throughput limit
    self.io_ratio = io_ratio # 1:1 for normal. compression - 0.5. decompression - 2.
    self.cpu_second = cpu_second # cpu second you need from input to output
    self.fixed_overhead = fixed_overhead
    pass

  # this is the possible output througput
  def passthrough(self, duration, input_size, input_rate):
    #
    my_cpu_time = input_size * self.cpu_second
    
    output_size = input_size * self.io_ratio

    output_rate = input_rate * self.io_ratio
    output_rate = min(output_rate, self.rate_limit) if self.rate_limit else output_rate
    my_throughput_time = output_size / output_rate

    return (max(my_throughput_time, my_cpu_time, duration) + self.fixed_overhead)
  pass


class E2E:
  def __init__(self):
    self.paths = []
    pass

  def add_path(self,path):
    self.paths.append(path)
    pass

  def compute(self, input_size):
    duration = 0
    input_size = input_size
    input_rate = 2**31 # something big enough
    for path in self.paths:
      output_duration, output_size, output_rate = path.passthrough(duration, input_size, input_rate)
      tlog.debug( "%8s: %6d (size: %6.1d, rate: %6.1d) --> %6d (size: %6.1d, rate: %6.1d)" % (path.name, duration, input_size/MiB, input_rate/MiB, output_duration, output_size/MiB, output_rate/MiB))
      duration = output_duration
      input_size = output_size
      input_rate = output_rate
      pass
    return duration
  pass

if __name__ == "__main__":
  e2e = E2E()
  # I'm the source file
  # Throughput(input_size=filesize, input_rate=None)

  # I'm the disk
  e2e.add_path(DataPath("disk", rate_limit=50 * MiB))

  # I'm the bus
  e2e.add_path(DataPath("bus", rate_limit=66 * MiB))

  # I'm the usb2
  #e2e.add_path(DataPath("usb2", rate_limit=6 * MiB))

  # I'm the compression
  e2e.add_path(DataPath("gzip", io_ratio=0.5, cpu_second=0.00000005))

  # I'm the network
  e2e.add_path(DataPath("e100", rate_limit=7 * MiB))

  print(e2e.compute(input_size=int(sys.argv[1]) * MiB))
  pass
