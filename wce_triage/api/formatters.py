from pydantic import BaseModel


class DiskInfo(BaseModel):
  target: int = 0
  deviceName: str
  runTime: float = 0
  runEstimate: float = 0
  mounted: bool
  size: int  # in MB (not MiB)
  bus: str
  model: str
  vendor: str
  serial_no: str
  smart: bool
  smart_enabled: bool
  pass


class OpticalDriveInfo(BaseModel):
  deviceName: str
  model: str
  pass


class NetworkDeviceStatus(BaseModel):
  device: str
  carrier: bool
  pass


class DiskImageInfo(BaseModel):
  """Shape of one entry from lib.disk_images.get_disk_images()."""
  mtime: str
  restoreType: str
  name: str
  fullpath: str
  size: int
  subdir: str
  index: int
  pass


def disk_info(disk) -> DiskInfo:
  return DiskInfo(target=0,
                  deviceName=disk.device_name,
                  runTime=0,
                  runEstimate=0,
                  mounted=disk.mounted,
                  size=round(disk.get_byte_size() / 1000000), # in MB (not MiB)
                  bus="usb" if disk.is_usb else "ata",
                  model=disk.model_name,
                  vendor=disk.vendor,
                  serial_no=disk.serial_no,
                  smart=disk.smart,
                  smart_enabled=disk.smart_enabled)

def optical_drive_info(optical) -> OpticalDriveInfo:
  return OpticalDriveInfo(deviceName=optical.device_name,
                          model=optical.vendor + " " + optical.model_name)

def network_device_status(netdev, carrier: bool) -> NetworkDeviceStatus:
  return NetworkDeviceStatus(device=netdev.device_name, carrier=carrier)

# Dict-returning wrappers, kept for the non-endpoint consumers (server.py's
# dispatch/equality-comparison path) that still work in plain dicts.
def jsoned_disk(disk) -> dict:
  return disk_info(disk).model_dump()

def jsoned_optical(optical) -> dict:
  return optical_drive_info(optical).model_dump()
