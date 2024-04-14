import os
import subprocess
import traceback

from fastapi.responses import FileResponse, JSONResponse
from fastapi import APIRouter, HTTPException, Query, status

from .. import op_save
from ..formatters import jsoned_disk, jsoned_optical
from ..internal.save_command import SaveCommandRunner
from ..internal.sync_command import SyncCommandRunner
from ..internal.unmount_command import UnmountCommandRunner
from ..internal.wipe_command import WipeCommandRunner
from ..internal.load_command import LoadCommandRunner
from ..models import Model
from ..internal.optical_drive import OpticalDriveTestRunner, OpticalDispatch
from ...lib.disk_images import read_disk_image_types, get_disk_images
from ...lib import get_triage_logger
from ...components import detect_sound_device, detect_optical_drives
from ..server import server
from ..operations import WIPE_TYPES
from ...components import network as _network

router = APIRouter()


# id: ID used for front/back communication
# name: displayed on web
# arg: arg used for restore image runner.
@router.get("/wipe-types")
def route_wipe_types():
  """Returning wipe types."""
  return {"wipeTypes": WIPE_TYPES}

#
#
@router.get("/triage")
def route_triage():
  """Handles requesting triage result"""
  return {"components": server.triage}


@router.get("/music")
def route_music():
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


@router.get("/messages")
def route_messages() -> JSONResponse:
  from ..messages import message_model
  return JSONResponse({"messages": [ message.get("message") for message in message_model.data.get("message", [])]})


# get_cpu_info is potentially ver slow for older computers as this runs a
# cpu benchmark.
@router.get("/cpu_info")
def route_cpu_info():
  """Handles getting CPU rating """
  return {"cpu_info": server.cpu_info}



@router.post("/save")
def save_disk_image(dName: str = Query(alias="deviceName"),
                    saveType: str = Query(alias="type"),
                    dest: str = Query(alias="destination", default=None),
                    partid: str = Query(alias="partition", default="Linux")):
  save_command_runner = server.get_runner(SaveCommandRunner)
  (result, code) = save_command_runner.queue_save(dName, saveType, dest, partid)
  return JSONResponse(result, status_code=code)


@router.post("/stop-save")
@router.post("/save/stop")
def stop_save() -> JSONResponse:
  runner_name = op_save
  save_command_runner = server.get_runner(runner_name)
  if save_command_runner is None:
    return JSONResponse({})
  save_command_runner.terminate()
  return JSONResponse({})


@router.get("/disk-save-status")
@router.get("/save/status")
def disk_save_status() -> JSONResponse:
  return JSONResponse(server._save_image.model.data)


@router.get("/disk-load-status")
@router.get("/load/status")
def disk_load_status() -> JSONResponse:
  tlog = get_triage_logger()
  tlog.debug(repr(server._load_image.model.data))
  return JSONResponse(server._load_image.model.data)


@router.get("/restore-types")
def route_restore_types() -> JSONResponse:
  """Returning supported restore types."""
  # disk image type is in lib/disk_images
  return JSONResponse({"restoreTypes": read_disk_image_types() })


@router.get("/disks")
def route_disks():
  """Handles getting the list of disks"""
  tlog = get_triage_logger()
  server.disk_portal.detect_disks()
  disks = [jsoned_disk(disk) for disk in server.disk_portal.disks]
  tlog.debug(str(disks))
  return JSONResponse({"diskPages": 1, "disks": disks})


@router.get("/opticaldrives")
def route_optical_drives():
  """Handles getting the list of disks"""
  opticals = [jsoned_optical(optical) for optical in server.opticals]
  tlog = get_triage_logger()
  tlog.debug(repr(opticals))
  return JSONResponse({"opticaldrives": opticals})


@router.get("/disk-images")
def route_disk_images():
  """Handles getting the list of disk images on local media"""
  # Loading doesn't have to come from http server, but this is a good test for now.
  disk_images = server.disk_image_file_path
  if os.path.exists(disk_images):
    return FileResponse(disk_images, status_code=200, media_type="application/json")
  return JSONResponse({"sources": server.disk_images })

@router.post("/load")
def route_load_image(
  devnames: str = Query(alias="deviceNames"),
  newhostname: str = Query(default=""),
  imagefile: str = Query(alias="source"),
  image_size: str | None = Query(alias="size", default=None, description="Image file size, if known"),
  restore_type: str = Query(alias="restoretype", description="Disk restore type"),
  wipe_request: str = Query(default="nowipe", description="Wipe request"),
):
  # WIPE_TYPES = [{"id": "nowipe", "name": "No Wipe", "arg": ""},
  #               {"id": "wipe", "name": "Full wipe", "arg": "-w"},
  #               {"id": "shortwipe", "name": "Wipe first 1Mb", "arg": "--quickwipe"}];

  target_disks = [disk.strip() for disk in devnames.split(',')]
  if not target_disks:
    return JSONResponse({"message": "No disk selected"}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

  load_command_runner = server.get_runner(LoadCommandRunner)

  for target_disk in target_disks:
    # FIXME: maybe report?
    _reply, _code = load_command_runner.queue_load(target_disk, restore_type, imagefile, image_size, wipe_request, newhostname)
    pass
  return JSONResponse({})


@router.post("/sync")
def route_sync_image(
  sources: str = Query(alias="sources"),
  devnames: str = Query(alias="deviceNames"),
):
  target_disks = [disk.strip() for disk in devnames.split(",")]
  sync_command_runner: SyncCommandRunner = server.get_runner(SyncCommandRunner)
  reply, status_code = sync_command_runner.queue_sync(sources.split(","), target_disks, clean=False)
  return JSONResponse(reply, status_code=status_code)

@router.get("/sync-status")
@router.get("/sync/status")
def route_sync_status() -> JSONResponse:
  return JSONResponse(server._sync_image.model.data)

@router.post("/clean")
def route_clean_image(
  devnames: str = Query(alias="deviceNames"),
):
  """clean disk images from the target disks"""
  target_disks = [disk.strip() for disk in devnames.split(",")]
  if not target_disks:
    return JSONResponse({"message": "No disk selected"}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
  sync_command_runner: SyncCommandRunner = server.get_runner(SyncCommandRunner)
  reply, status_code = sync_command_runner.queue_sync([], target_disks, clean=True)
  return JSONResponse(reply, status_code=status_code)


@router.post("/delete")
def route_delete_image(
  name: str = Query(alias="name"),
  restoretype: str = Query(alias="restoretype"),
):
  tlog = get_triage_logger()

  for disk_image in get_disk_images():
    if disk_image['name'] != name or disk_image['restoreType'] != restoretype:
      continue

    fullpath = disk_image['fullpath']
    try:
      tlog.debug("Delete '%s'" % fullpath)
      os.remove(fullpath)
      tlog.debug("Delete '%s' succeeded." % fullpath)
      return JSONResponse({})
    except Exception as _exc:
      # FIXME: better response?
      msg = "Delete '%s' failed.\n%s" % (fullpath, traceback.format_exc())
      tlog.info(msg)
      return JSONResponse({}, status_code=status.HTTP_400_BAD_REQUEST)
    pass
  return JSONResponse({}, status_code=status.HTTP_404_NOT_FOUND)


@router.post("/rename")
def route_rename_image(
  name_from: str = Query(alias="from"),
  name_to: str = Query(alias="to"),
  restoretype: str = Query(alias="restoretype"),
) -> JSONResponse:
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
      # FIXME: better response?
      tlog.info("RENAME failed - %s/%s." % (restoretype, name_from), exc_info=True)
      return JSONResponse({}, status_code=status.HTTP_404_NOT_FOUND)
    except Exception as _exc:
      # FIXME: better response?
      tlog.info("RENAME failed - %s/%s." % (restoretype, name_from), exc_info=True)
      return JSONResponse({"message": traceback.format_exc()}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
      pass
  return JSONResponse({})


@router.post("/mount")
def route_mount_disk(
  requested: str = Query(alias="deviceName"),
):
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
        return JSONResponse({}, status_code=status.HTTP_400_BAD_REQUEST)
      pass
    pass
  return JSONResponse({})

@router.post("/wipe")
def route_wipe_disks(
  devnames: str = Query(alias="deviceNames"),
):
  target_disks = [disk.strip() for disk in devnames.split(",")]
  if not target_disks:
    return JSONResponse({"message": "No disks selected"}, status_code=status.HTTP_400_BAD_REQUEST)

  wipe_command_runner:WipeCommandRunner = server.get_runner(WipeCommandRunner)
  result, code = wipe_command_runner.queue_wipe(target_disks)
  return JSONResponse(result, status_code=code)


def stop_runner(runner_class) -> JSONResponse:
  runner = server.get_runner(runner_class, create=False)
  if runner:
    runner.terminate()
    pass
  return JSONResponse({})

@router.get("/wipe/status")
def disk_wipe_status() -> JSONResponse:
  #tlog = get_triage_logger()
  #tlog.debug(repr(server._load_image.model.data))
  #return server._load_image.model.data
  return JSONResponse(server._wipe_disk.model.data)


@router.post("/stop-load")
@router.post("/load/stop")
def route_stop_load_image() -> JSONResponse:
  return stop_runner(LoadCommandRunner)


@router.post("/stop-save")
@router.post("/save/stop")
def route_stop_save_image() -> JSONResponse:
  return stop_runner(SaveCommandRunner)

@router.post("/stop-wipe")
@router.post("/wipe/stop")
def route_stop_disk_wipe() -> JSONResponse:
  return stop_runner(WipeCommandRunner)

@router.post("/stop-sync")
@router.post("/sync/stop")
def route_stop_sync() -> JSONResponse:
  return stop_runner(SyncCommandRunner)


@router.post("/shutdown")
def route_shutdown(
    shutdown_mode: str = Query(alias="mode", default="ignored")
) -> JSONResponse:
  """shutdowns the computer."""
  if shutdown_mode == "poweroff":
    subprocess.run(['poweroff'])
  elif shutdown_mode == "reboot":
    subprocess.run(['reboot'])
  else:
    return JSONResponse({}, status_code=status.HTTP_400_BAD_REQUEST)
  return JSONResponse({})


@router.get("/network-device-status")
def route_network_device_status() -> JSONResponse:
  """Network status"""
  netstat = []
  for netdev in _network.detect_net_devices():
    netstat.append({"device": netdev.device_name, "carrier": netdev.is_network_connected()})
    server.update_component_decision(
      {"component": "Network", "device": netdev.device_name},
      {"result": netdev.is_network_connected(),
       "message": "Connection detected." if netdev.is_network_connected() else "Not conntected."})
    pass
  return JSONResponse(netstat)

@router.post("/unmount")
def route_unmount(
  devnames: str = Query(alias="deviceNames"),
):
  target_disks = [disk.strip() for disk in devnames.split(",")]
  unmount_command_runner: UnmountCommandRunner = server.get_runner(UnmountCommandRunner)
  result, code = unmount_command_runner.queue_unmount(target_disks)
  return JSONResponse(result, status_code=code)


@router.post("/opticaldrive/test")
def route_opticaldrive_test():
  """Test optical drive"""
  global optical_dispatch

  opticals = server.opticals
  if opticals.count() == 0:
    od = detect_optical_drives()
    if len(od) == 0:
      return JSONResponse({"message": "No optical drives"}, status_code=status.HTTP_404_NOT_FOUND)
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
  for optical in opticals.drives:
    tlog.debug("run wce_triage.bin.test_optical " + optical.device_name)
    runner.queue_test(optical.device_name)
    pass
  # This is meaningless.
  return JSONResponse({"message": "OK"})
