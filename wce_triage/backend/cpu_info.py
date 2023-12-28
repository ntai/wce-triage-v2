
from .models import Model

class CpuInfoModel(Model):
  @property
  def data(self):
    from ..lib.cpu_info import get_cpu_info
    if self.model_state is None:
      self.model_state = True
      cpu_info = get_cpu_info()
      self.set_model_data(cpu_info)
      pass
    return self._model


  pass