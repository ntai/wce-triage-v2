from .models import Model
import subprocess

from ..lib.util import get_triage_logger

def get_cpu_info(self):
  tlog = get_triage_logger()

  tlog.debug("get_cpu_info: starting")
  cpu_info = subprocess.Popen("python3 -m wce_triage.lib.cpu_info", shell=True, stdout=subprocess.PIPE,
  stderr=subprocess.PIPE)
  tlog.debug("get_cpu_info: started")
  (out, err) = self.cpu_info.communicate()
  tlog.debug("get_cpu_info: ended")
  return (out, err)

class CpuInfoModel(Model):
  @property
  def data(self):
    if self.model_state is None:
      self.model_state = True
      (out, err) = get_cpu_info()
      self.set_model_data(out)
      pass
    return self._model
