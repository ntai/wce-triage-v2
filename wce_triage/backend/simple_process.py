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

#
#
class CpuInfoCommandRunner(ProcessRunner):
  returncode: Optional[int]
  # This is to receive the stream
  out: StreamModel
  err: StreamModel
  _cpu_info: Model

  @classmethod
  def class_name(cls):
    return "cpu_info"

  def __init__(self, cpu_info: Model):
    self.returncode = None
    self.out = StreamModel()
    self.err = StreamModel()
    self._cpu_info = cpu_info
    super().__init__(stdout_dispatch=ModelDispatch(self.out),
                     stderr_dispatch=ModelDispatch(self.err),
                     meta={"tag": "cpu_info"})
    pass

  def start(self):
    super().start()
    args = ['python3', '-m', 'wce_triage.lib.cpu_info']
    self.queue(args, {"job": "cpu_info"})
    self.queue(None, {})
    self.join()

    if self.returncode == 0:
      self._cpu_info.dispatch(json.loads(str(self.out)))
      pass
    else:
      self._cpu_info.dispatch({"output": str(out), "error": str(err), "returncode": returncode})
      pass
    pass

  def test(self):
    self.start()
    args = ['/bin/bash', '-c', 'echo hello']
    self.queue(args, {"job": "cpu_info"})
    self.queue(None, {})
    self.join()
    return self.out, self.err, self.returncode


  def process_ended(self, result):
    self.returncode = self.process.returncode
    pass

  pass


if __name__ == "__main__":
  cpu_info = CpuInfoCommandRunner()
  (out, err, returncode) = cpu_info.test()
  print(returncode)
  print(out)
  print(err)