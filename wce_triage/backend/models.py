from wce_triage.components.disk import DiskPortal


class Model(object):
  model: dict

  def __init__(self):
    self.model = {}
    pass

  def set_model_data(self, new_data):
    point_a = set(self.model.items())
    point_b = set(self.new_data.items())
    self.model = new_data
    self.view.update(point_a - point_b, point_b - point_a)
    pass


  pass


class DiskModel(Model):
  disk_portal: DiskPortal

  def __init__(self):
    self.disk_portal = {}
    pass

  def refresh_disks(self):
    self.set_model_data(DiskPortal())

  pass
