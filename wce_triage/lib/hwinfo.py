import os, subprocess, json
import logging
tlog = logging.getLogger('triage')

# lshw is far better!
def run_lshw():
  lshw = subprocess.Popen(['sudo', '-H', '-S', 'lshw', '-json'], stderr=subprocess.PIPE, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
  password = os.environ.get('WCE_TEST_PASSWORD', 'wce123')
  (out, err) = lshw.communicate(password.encode('iso-8859-1'))
  if out == b'':
    return None
  if err != b'':
    tlog.debug(err)
    pass
  return json.loads(out)


def find_class(found_func, data, class_name):
  if data == None:
    return None

  if data.get('class') == class_name:
    found_func(data)
    pass

  children = data.get('children')
  if children:
    for child in children:
      find_class(found_func, child, class_name)
      pass
    pass
  pass
      

class hw_info:
  def __init__(self):
    self.lshw = run_lshw()
    pass

  def _collector(self, data):
    self.collection.append(data)
    pass

  def get_entries(self, class_name):
    self.collection = []
    find_class(self._collector, self.lshw, class_name)
    return self.collection[:]
  pass


if __name__ == "__main__":
  hwi = hw_info()
  for entry in hwi.get_entries('network'):
    print(entry)
    pass
  pass
