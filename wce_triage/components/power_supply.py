#!/usr/bin/python3
# Copyright (c) 2023 Naoyuki tai
# MIT license - see LICENSE

from .component import Component
import os.path

psu_props = ["alarm",
             "capacity",
             "capacity_level",
             "charge_control_end_threshold",
             "cycle_count",
             "energy_full",
             "energy_full_design",
             "energy_now",
             "manufacturer",
             "model_name",
             "online",
             "power_now",
             "present",
             "serial_number",
             "status",
             "technology",
             "type",
             "voltage_min_design",
             "voltage_now"]


def get_psu_prop(psu):
  props = {}
  for prop in psu_props:
    try:
      with open(os.path.join(psu, prop), encoding="ascii") as psu_prop_fd:
        props[prop] = psu_prop_fd.read().strip()
        pass
      pass
    except FileNotFoundError:
      pass
    except:
      pass
    pass
  return props


def detect_power_supply():
  psu_path = "/sys/class/power_supply"
  psus = []
  try:
    for psu in os.listdir(psu_path):
      psus.append(get_psu_prop(os.path.join(psu_path, psu)))
      pass
    pass
  except:
    pass
  return psus


class PowerSupply(Component):

  def __init__(self):
    self.psus = detect_power_supply()
    pass

  def get_component_type(self):
    return "Power"

  def decision(self, **kwargs):
    if not self.psus:
      return [{"component": self.get_component_type(),
               "result": False,
               "message": "Battery: None"}]
      pass
    else:
      return [{"component": self.get_component_type(),
               "result": True,
               "message": self.render_prop(psu)} for psu in self.psus]
    pass

  def render_prop(self, psu):
    p_type = psu.get("type")
    if p_type == "Battery":
      reports = []
      if "energy_full" in psu and "energy_full_design" in psu:
        full_t0 = float(psu["energy_full_design"])
        full_now = float(psu["energy_full"])
        reports.append("Health: %d%%" % round(full_now / full_t0 * 100.0))
        pass

      if "energy_full" in psu and "energy_now" in psu:
        full_now = float(psu["energy_full"])
        charge = float(psu["energy_now"])
        reports.append("Charge: %d%%" % round(charge / full_now * 100.0))
        pass

      if "cycle_count" in psu:
        reports.append("Cycle count " + psu["cycle_count"])
        pass
      if "status" in psu:
        reports.append("Battery is " + psu["status"])
        pass
      if "manufacturer" in psu:
        reports.append(psu["manufacturer"])
        pass
      if "model_name" in psu:
        reports.append("Model: " + psu["model_name"])
        pass
      if "serial_number" in psu:
        reports.append("SN: " + psu["serial_number"])
        pass
      if "technology" in psu:
        reports.append("Material: " + psu["technology"])
        pass
      if "energy_full_design" in psu:
        full_t0 = float(psu["energy_full_design"])
        # Unit is microwatt hours
        reports.append("Design capacity: %dWh" % round(full_t0 / 1000000.0))
        pass
      return "Battery " + ", ".join(reports)
    elif p_type == "Mains":
      reports = []
      if "online" in psu:
        if psu["online"] == "1":
          reports.append("AC on")
        else:
          reports.append("AC off")
          pass
        pass
      return "Power suppy " + ", ".join(reports)
    return repr(psu)

  pass


#
if __name__ == "__main__":
  battery = PowerSupply()
  print(battery.decision())
  pass
