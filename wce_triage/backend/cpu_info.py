from .models import Model
import subprocess
import os
import sys

from ..lib.util import get_triage_logger
from ..lib.cpu_info import get_cpu_info

class CpuInfoModel(Model):
  @property
  def data(self):
    if self.model_state is None:
      self.model_state = True
      cpu_info = get_cpu_info()
      self.set_model_data(cpu_info)
      pass
    return self._model
