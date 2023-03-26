import re

def get_ubuntu_release():
  release_re = re.compile( 'DISTRIB_RELEASE\s*=\s*(\d+\.\d+)' )
  with open('/etc/lsb-release') as lsb_release_fd:
    for line in lsb_release_fd.readlines():
      result = release_re.search(line)
      if result:
        return result.group(1)
      pass
    pass
  return None

