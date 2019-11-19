# Copyright (c) 2019 Naoyuki tai
# MIT license - see LICENSE
"""cpubench gets the cpu perf. 
Currently, this uses hardinfo.
"""

import subprocess, json

from .util import get_triage_logger
tlog = get_triage_logger()

global cpu_info
#
# Baseline is Intel Core 2 Duo T7300 2GHz
# This is probably the low end Core2 Duo
#

benchmarks = {
  'CPU Blowfish':   {"baseline": 8.300564},
  'CPU CryptoHash': {"baseline": 1.748670},
  'CPU Fibonacci' : {"baseline": 4.263994},
  'CPU N-Queens' : {"baseline":  9.347419},
  'CPU Zlib' : {"baseline": 19.856069},
  'FPU FFT': {"baseline": 4.366442},
  'FPU Raytracing':{"baseline": 12.173288}
}

cpu_info = { 'benchmarks': benchmarks }


def get_cpu_info():
  global cpu_info

  if 'rating' in cpu_info:
    return cpu_info

  hardinfo = subprocess.run(["hardinfo", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  output = hardinfo.stdout.decode('iso-8859-1')
  if output.splitlines()[0].strip() != 'HardInfo version 0.6-alpha':
    cpu_info['rating'] = 'Unknown due to incompatible hardinfo version'
    return cpu_info

  hardinfo = subprocess.run(["hardinfo", "-r", "-f", "text"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  output = hardinfo.stdout.decode('iso-8859-1')
  bm_results = output.splitlines()[:15]
  
  benchmarks = cpu_info['benchmarks']
  first = True
  scores = []
  
  while len(bm_results) > 1:
    bm_name = bm_results[0][1:-1]
    bm_result = bm_results[1]
    bm_results = bm_results[2:]

    if bm_name in benchmarks:
      bm_columns = bm_result.split('|')
      if first:
        first = False
        cpu_info['machine'] = bm_columns[1]
        cpu_info['board'] = bm_columns[2]
        cpu_info['name'] = bm_columns[3]
        cpu_info['description'] = bm_columns[4]
        cpu_info['config'] = bm_columns[5]
        cpu_info['memory_size'] = bm_columns[6]
        cpu_info['n_processors'] = bm_columns[7]
        cpu_info['n_physical_cores'] = bm_columns[8]
        cpu_info['n_logical_cores'] = bm_columns[9]
        pass
      details = bm_columns[0].split(';')

      result = float(details[3])
      # n_threas = details[4]

      benchmark = benchmarks[bm_name]
      normalized_score = None
      if 'baseline' in benchmark:
        normalized_score = benchmark['baseline'] / result
      elif 'baseline-count' in benchmark:
        normalized_score = result / benchmark['baseline-count']
        pass
      if normalized_score:
        benchmark['score'] = normalized_score
        scores.append(normalized_score)
        pass
      pass
    pass

  cpu_info['rating'] = str(round(sum(scores) / len(scores), 2))
  return cpu_info
      

if __name__ == "__main__":
  print(json.dumps(get_cpu_info()))
  pass
