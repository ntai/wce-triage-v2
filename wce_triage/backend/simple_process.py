import sys

from .models import Model, ModelDispatch
from .process_runner import ProcessRunner
from typing import Optional
import io
import json

class StreamModel(Model):
  _data: io.BytesIO

  def __init__(self, key="stream", meta=None, default=None):
    self._data = io.StringIO()
    self._model = {"data": self._data}
    super().__init__(cumulative=True, key=key, meta=meta, default=default)
    pass

  def set_model_data(self, data):
    self.lock.acquire()
    try:
      self.model_state = True
      self._data.write(data)
      pass
    finally:
      self.lock.release()
      pass
    pass

  def clear(self, default=None):
    self._data.seek(0)
    pass

  def __str__(self):
    return self._data.getvalue()

  def json(self):
    return json.loads(self._data.getvalue())

#
#
class CpuInfoCommandRunner(ProcessRunner):
  returncode: Optional[int]
  # This is to receive the stream
  _cpu_info: ModelDispatch

  @classmethod
  def class_name(cls):
    return "cpu_info"

  def __init__(self, cpu_info: ModelDispatch):
    self.returncode = None
    self._cpu_info = cpu_info
    super().__init__(stdout_dispatch=self._cpu_info,
                     stderr_dispatch=None,
                     meta={"tag": "cpu_info"})
    pass

  def start(self):
    super().start()
    args = [sys.executable, '-m', 'wce_triage.lib.cpu_info']
    self.queue(args, {"job": "cpu_info"})
    self.queue(None, {})
    self.join()

    if self.returncode != 0:
      self._cpu_info.model.set_model_data({"output": self._cpu_info.model.data, "returncode": returncode})
      pass
    pass

  def test(self):
    self.start()
    args = ['/bin/bash', '-c', 'echo hello']
    self.queue(args, {"job": "cpu_info"})
    self.queue(None, {})
    self.join()
    return self._cpu_info.model.data, self.returncode


  def process_ended(self, result):
    self.returncode = self.process.returncode
    pass

  pass


if __name__ == "__main__":
  from wce_triage.backend.cpu_info import CpuInfoModel
  model = CpuInfoModel()
  cpu_info = ModelDispatch(model)
  runner = CpuInfoCommandRunner(cpu_info)
  (out, returncode) = runner.test()
  print(returncode)
  print(out)
