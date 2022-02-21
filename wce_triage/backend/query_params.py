
def get_target_devices_from_request(request):
  devname = request.args.get("deviceName")
  devnames = request.args.get("deviceNames")

  # devices to load
  if devnames is not None:
    target_disks = devnames.split(',')
    pass
  elif devname and devnames is None:
    target_disks = [devname]
  else:
    target_disks = None
    pass
  return target_disks
