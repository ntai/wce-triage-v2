import os
import subprocess
import traceback
from fastapi.responses import FileResponse
from fastapi import APIRouter, HTTPException, Query, status

from pydantic import BaseModel
from typing import List, Optional

from .. import op_save
from ..formatters import disk_info, optical_drive_info, network_device_status, DiskInfo, OpticalDriveInfo, DiskImageInfo, NetworkDeviceStatus, CpuInfo, DiskImageType
from ...ops.protocol import OperationProgress
from ...ops.run_state import RunState
from ..socket_protocol import TriageUpdateEvent
from ..internal.save_command import SaveCommandRunner
from ..internal.sync_command import SyncCommandRunner
from ..internal.unmount_command import UnmountCommandRunner
from ..internal.wipe_command import WipeCommandRunner
from ..internal.load_command import LoadCommandRunner
# from ..messages import UserMessages
from ..models import Model
from ..internal.optical_drive import OpticalDriveTestRunner, OpticalDispatch
from ...lib.disk_images import read_disk_image_types, get_disk_images
from ...lib import get_triage_logger
from ...components import detect_sound_device, detect_optical_drives
from ..server import server
from ..operations import WIPE_TYPES
from ...components import network as _network
from ..socket_protocol import DisksEvent, LogMessageEvent

router = APIRouter()


# Schema-only stubs: DisksEvent/LogMessageEvent are socket.io-only payloads (see
# api/socket_protocol.py) with no REST equivalent, so nothing calls these routes -
# they exist purely so openapi-typescript picks the models up into triage-api.ts,
# the same way OperationProgress/TriageUpdateEvent already do via their real routes.
@router.get("/schema/disks-event", include_in_schema=True)
def _disks_event_schema() -> DisksEvent:
  return DisksEvent(disks=[])


@router.get("/schema/log-message-event", include_in_schema=True)
def _log_message_event_schema() -> LogMessageEvent:
  return LogMessageEvent(message="", severity=1)


class WipeType(BaseModel):
  id: str          # ID used for front/back communication
  name: str         # displayed on web
  arg: Optional[str] = None   # arg used for restore image runner.


class WipeTypesResponse(BaseModel):
  wipeTypes: List[WipeType]


@router.get("/wipe-types")
def route_wipe_types() -> WipeTypesResponse:
  """Returning wipe types."""
  return WipeTypesResponse(wipeTypes=WIPE_TYPES)

#
#
@router.get("/triage", response_model_exclude_none=True)
def route_triage() -> TriageUpdateEvent:
  """Handles requesting triage result"""
  return TriageUpdateEvent(**server.triage)


@router.get("/music")
def route_music() -> FileResponse:
  """Send ogg/mp3 stream to browser"""
  # For now, return the first mp3 file. Triage usually has only one
  # mp3 file for space reason.

  music_file = None
  asset_path = server.asset_path
  filetype = "mp3"
  for asset in os.listdir(asset_path):
    if asset.endswith(".ogg"):
      music_file = os.path.join(asset_path, asset)
      filetype = "ogg"
      break
    pass

  if not music_file:
    for asset in os.listdir(asset_path):
      if asset.endswith(".mp3"):
        music_file = os.path.join(asset_path, asset)
        break
      pass
    pass

  if not music_file:
    raise HTTPException(status_code=404, detail="No music files")

  if detect_sound_device():
    server.update_component_decision({"component": "Sound"},
                                     {"result": True, "message": "Sound is tested."})
  return FileResponse(music_file, media_type=f"audio/{filetype}")


class CpuInfoResponse(BaseModel):
  cpu_info: CpuInfo


# get_cpu_info is potentially ver slow for older computers as this runs a
# cpu benchmark.
@router.get("/cpu_info")
def route_cpu_info() -> CpuInfoResponse:
  """Handles getting CPU rating """
  cpu_info = server.cpu_info
  if cpu_info is None:
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="CPU info not available")
  return CpuInfoResponse(cpu_info=cpu_info)



@router.post("/save")
def save_disk_image(dName: str = Query(alias="deviceName"),
                    saveType: str = Query(alias="type"),
                    dest: str = Query(alias="destination", default=None),
                    partid: str = Query(alias="partition", default="Linux")) -> OperationProgress:
  save_command_runner = server.get_runner(SaveCommandRunner)
  return save_command_runner.queue_save(dName, saveType, dest, partid)


@router.post("/stop-save")
@router.post("/save/stop")
def stop_save() -> None:
  runner_name = op_save
  save_command_runner = server.get_runner(runner_name)
  if save_command_runner is None:
    return
  save_command_runner.terminate()
  return


@router.get("/disk-save-status")
@router.get("/save/status")
def disk_save_status() -> OperationProgress:
  return OperationProgress(**server._save_image.model.data)


@router.get("/disk-load-status")
@router.get("/load/status")
def disk_load_status() -> OperationProgress:
  tlog = get_triage_logger()
  tlog.debug(repr(server._load_image.model.data))
  return OperationProgress(**server._load_image.model.data)


class RestoreTypesResponse(BaseModel):
  restoreTypes: List[DiskImageType]


@router.get("/restore-types")
def route_restore_types() -> RestoreTypesResponse:
  """Returning supported restore types."""
  # disk image type is in lib/disk_images
  return RestoreTypesResponse(restoreTypes=[DiskImageType(**t) for t in read_disk_image_types()])


class DisksResponse(BaseModel):
  diskPages: int
  disks: List[DiskInfo]


@router.get("/disks")
def route_disks() -> DisksResponse:
  """Handles getting the list of disks"""
  tlog = get_triage_logger()
  server.disk_portal.detect_disks()
  disks = [disk_info(disk) for disk in server.disk_portal.disks]
  tlog.debug(str(disks))
  return DisksResponse(diskPages=1, disks=disks)


class OpticalDrivesResponse(BaseModel):
  opticaldrives: List[OpticalDriveInfo]


@router.get("/opticaldrives")
def route_optical_drives() -> OpticalDrivesResponse:
  """Handles getting the list of disks"""
  opticals = [optical_drive_info(optical) for optical in server.opticals]
  tlog = get_triage_logger()
  tlog.debug(repr(opticals))
  return OpticalDrivesResponse(opticaldrives=opticals)


class DiskImagesResponse(BaseModel):
  sources: List[DiskImageInfo]


@router.get("/disk-images")
def route_disk_images() -> DiskImagesResponse:
  """Handles getting the list of disk images on local media"""
  # Loading doesn't have to come from http server, but this is a good test for now.
  disk_images = server.disk_image_file_path
  if os.path.exists(disk_images):
    # Pre-generated by bin/generate_image_list.py - served verbatim, not re-validated.
    return FileResponse(disk_images, status_code=200, media_type="application/json")
  return DiskImagesResponse(sources=[DiskImageInfo(**source) for source in server.disk_images])

@router.post("/load")
def route_load_image(
  devnames: str = Query(alias="deviceNames"),
  newhostname: str = Query(default=""),
  imagefile: str = Query(alias="source"),
  image_size: str | None = Query(alias="size", default=None, description="Image file size, if known"),
  restore_type: str = Query(alias="restoretype", description="Disk restore type"),
  wipe_request: str = Query(default="nowipe", description="Wipe request"),
) -> OperationProgress:
  # WIPE_TYPES = [{"id": "nowipe", "name": "No Wipe", "arg": ""},
  #               {"id": "wipe", "name": "Full wipe", "arg": "-w"},
  #               {"id": "shortwipe", "name": "Wipe first 1Mb", "arg": "--quickwipe"}];

  target_disks = [disk.strip() for disk in devnames.split(',')]
  if not target_disks:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No disk selected")

  load_command_runner = server.get_runner(LoadCommandRunner)

  for target_disk in target_disks:
    load_command_runner.queue_load(target_disk, restore_type, imagefile, image_size, wipe_request, newhostname)
    pass
  return OperationProgress(**server._load_image.model.data)


@router.post("/sync")
def route_sync_image(
  sources: str = Query(alias="sources"),
  devnames: str = Query(alias="deviceNames"),
) -> OperationProgress:
  target_disks = [disk.strip() for disk in devnames.split(",")]
  sync_command_runner: SyncCommandRunner = server.get_runner(SyncCommandRunner)
  return sync_command_runner.queue_sync(sources.split(","), target_disks, clean=False)

@router.get("/sync-status", operation_id="route_sync_status")
@router.get("/sync/status", operation_id="route_sync_status_alt")
def route_sync_status() -> OperationProgress:
  return OperationProgress(**server._sync_image.model.data)

@router.post("/clean")
def route_clean_image(
  devnames: str = Query(alias="deviceNames"),
) -> OperationProgress:
  """clean disk images from the target disks"""
  target_disks = [disk.strip() for disk in devnames.split(",")]
  if not target_disks:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No disk selected")
  sync_command_runner: SyncCommandRunner = server.get_runner(SyncCommandRunner)
  return sync_command_runner.queue_sync([], target_disks, clean=True)


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
def route_delete_image(
  name: str = Query(alias="name"),
  restoretype: str = Query(alias="restoretype"),
) -> None:
  tlog = get_triage_logger()

  for disk_image in get_disk_images():
    if disk_image['name'] != name or disk_image['restoreType'] != restoretype:
      continue

    fullpath = disk_image['fullpath']
    try:
      tlog.debug("Delete '%s'" % fullpath)
      os.remove(fullpath)
      tlog.debug("Delete '%s' succeeded." % fullpath)
      return
    except Exception as _exc:
      msg = "Delete '%s' failed.\n%s" % (fullpath, traceback.format_exc())
      tlog.info(msg)
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
  raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Disk image not found")


@router.post("/rename")
def route_rename_image(
  name_from: str = Query(alias="from"),
  name_to: str = Query(alias="to"),
  restoretype: str = Query(alias="restoretype"),
) -> None:
  tlog = get_triage_logger()

  for disk_image in get_disk_images():
    if disk_image['name'] != name_from or disk_image['restoreType'] != restoretype:
      continue

    fullpath = disk_image['fullpath']
    parent_dir = os.path.split(fullpath)[0]
    to_path = os.path.join(parent_dir, name_to)
    try:
      os.rename(fullpath, to_path)
      break
    except IOError:
      tlog.info("RENAME failed - %s/%s." % (restoretype, name_from), exc_info=True)
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    except Exception as _exc:
      tlog.info("RENAME failed - %s/%s." % (restoretype, name_from), exc_info=True)
      raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=traceback.format_exc())
  return


@router.post("/mount")
def route_mount_disk(
  requested: str = Query(alias="deviceName"),
) -> None:
  """Mount disk"""
  portal = server.disk_portal
  portal.detect_disks()
  disks = portal.disks

  for disk in disks:
    if disk.device_name in requested:
      try:
        mount_point = disk.device_name.get_mount_point()
        if not os.path.exists(mount_point):
          os.mkdir(mount_point)
          pass
        subprocess.run(["mount", disk.device_name, mount_point])
        pass
      except Exception as _exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(_exc))
      pass
    pass
  return

@router.post("/wipe")
def route_wipe_disks(
  devnames: str = Query(alias="deviceNames"),
) -> OperationProgress:
  target_disks = [disk.strip() for disk in devnames.split(",")]
  if not target_disks:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No disks selected")

  wipe_command_runner:WipeCommandRunner = server.get_runner(WipeCommandRunner)
  return wipe_command_runner.queue_wipe(target_disks)


def stop_runner(runner_class) -> None:
  runner = server.get_runner(runner_class, create=False)
  if runner:
    runner.terminate()
    pass
  return

@router.get("/wipe/status")
def disk_wipe_status() -> OperationProgress:
  return OperationProgress(**server._wipe_disk.model.data)


@router.post("/stop-load")
@router.post("/load/stop")
def route_stop_load_image() -> OperationProgress:
  stop_runner(LoadCommandRunner)
  return OperationProgress(**server._load_image.model.data)


@router.post("/stop-save")
@router.post("/save/stop")
def route_stop_save_image() -> OperationProgress:
  stop_runner(SaveCommandRunner)
  return OperationProgress(**server._save_image.model.data)


@router.post("/stop-wipe")
@router.post("/wipe/stop")
def route_stop_disk_wipe() -> OperationProgress:
  stop_runner(WipeCommandRunner)
  return OperationProgress(**server._wipe_disk.model.data)


@router.post("/stop-sync")
@router.post("/sync/stop")
def route_stop_sync() -> OperationProgress:
  stop_runner(SyncCommandRunner)
  return OperationProgress(**server._sync_image.model.data)


@router.post("/shutdown")
def route_shutdown(
    shutdown_mode: str = Query(alias="mode", default="ignored")
) -> None:
  """shutdowns the computer."""
  if shutdown_mode == "poweroff":
    subprocess.run(['poweroff'])
  elif shutdown_mode == "reboot":
    subprocess.run(['reboot'])
  else:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid shutdown mode")
  return


@router.get("/network-device-status")
def route_network_device_status() -> List[NetworkDeviceStatus]:
  """Network status"""
  netstat: List[NetworkDeviceStatus] = []
  for netdev in _network.detect_net_devices():
    connected = netdev.is_network_connected()
    netstat.append(network_device_status(netdev, connected))
    server.update_component_decision(
      {"component": "Network", "device": netdev.device_name},
      {"result": connected,
       "message": "Connection detected." if connected else "Not conntected."})
    pass
  return netstat

@router.post("/unmount")
def route_unmount(
  devnames: str = Query(alias="deviceNames"),
) -> OperationProgress:
  target_disks = [disk.strip() for disk in devnames.split(",")]
  unmount_command_runner: UnmountCommandRunner = server.get_runner(UnmountCommandRunner)
  return unmount_command_runner.queue_unmount(target_disks)


@router.post("/opticaldrive/test")
def route_opticaldrive_test() -> OperationProgress:
  """Test optical drive"""
  global optical_dispatch

  opticals = server.opticals
  if opticals.count() == 0:
    od = detect_optical_drives()
    if len(od) == 0:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No optical drives")
    else:
      server.update_triage()
      opticals = server.opticals
      pass

  tlog = get_triage_logger()
  runner = server.get_runner(OpticalDriveTestRunner, create=False)
  if runner is None:
    optical_dispatch = OpticalDispatch(Model())
    runner = OpticalDriveTestRunner(optical_dispatch)
    server.register_runner(runner)
    runner.start()
    pass

  # Since reading optical is slow, the answer goes back over websocket.
  devnames = []
  for optical in opticals.drives:
    tlog.debug("run wce_triage.bin.test_optical " + optical.device_name)
    runner.queue_test(optical.device_name)
    devnames.append(optical.device_name)
    pass
  return OperationProgress(report="tasks", device=",".join(devnames), runStatus=RunState.Initial,
                           runMessage="", tasks=[])
