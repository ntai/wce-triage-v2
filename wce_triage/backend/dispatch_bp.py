import os
import subprocess
import traceback

from . import op_save
from .formatters import jsoned_disk, jsoned_optical
from .optical_drive import route_opticaldrivetest
from .query_params import get_target_devices_from_request
from .save_command import SaveCommandRunner
from .sync_command import SyncCommandRunner
from .unmount_command import UnmountCommandRunner
from .wipe_command import WipeCommandRunner
from ..lib.disk_images import read_disk_image_types, get_disk_images
from ..lib import get_triage_logger
from flask import jsonify, send_file, Blueprint, request
from ..components import detect_sound_device
from .server import server
from http import HTTPStatus
from .operations import WIPE_TYPES
from .load_command import LoadCommandRunner
from ..components import network as _network


dispatch_bp = Blueprint('dispatch', __name__, url_prefix='/dispatch')

# id: ID used for front/back communication
# name: displayed on web
# arg: arg used for restore image runner.
@dispatch_bp.route("/wipe-types.json")
@dispatch_bp.route("/wipe-types")
def route_wipe_types():
  """Returning wipe types."""
  return jsonify({"wipeTypes": WIPE_TYPES})

#
#
@dispatch_bp.route("/triage.json")
@dispatch_bp.route("/triage")
def route_triage():
  """Handles requesting triage result"""
  return {"components": server.triage}


@dispatch_bp.route("/music")
def route_music():
  """Send mp3 stream to chrome"""
  # For now, return the first mp3 file. Triage usually has only one
  # mp3 file for space reason.

  music_file = None
  asset_path = server.asset_path
  for asset in os.listdir(asset_path):
    if asset.endswith(".ogg"):
      music_file = os.path.join(asset_path, asset)
      break
    pass

  if music_file:
    res = send_file(music_file, mimetype="audio/" + music_file[-3:])
    if detect_sound_device():
      server.update_component_decision({"component": "Sound"},
                                       {"result": True, "message": "Sound is tested."})
      pass
    return res
  return {}, HTTPStatus.NOT_FOUND


@dispatch_bp.route("/messages")
def route_messages():
  from .messages import message_model
  return { "messages": [ message.get("message") for message in message_model.data.get("message", [])]}


# get_cpu_info is potentially ver slow for older computers as this runs a
# cpu benchmark.
@dispatch_bp.route("/cpu_info.json")
@dispatch_bp.route("/cpu_info")
def route_cpu_info():
  """Handles getting CPU rating """
  return { "cpu_info": server.cpu_info }


@dispatch_bp.route("/save", methods=["POST"])
def save_disk_image():
  devname = request.args.get("deviceName")
  saveType = request.args.get("type")
  destdir = request.args.get("destination")
  partid = request.args.get("partition", default="Linux")
  save_command_runner = server.get_runner(SaveCommandRunner)
  (result, code) = save_command_runner.queue_save(devname, saveType, destdir, partid)
  return result, code


@dispatch_bp.route("/stop-save", methods=["POST"])
@dispatch_bp.route("/save/stop", methods=["POST"])
def stop_save():
  runner_name = op_save
  save_command_runner = server.get_runner(runner_name)
  if save_command_runner is None:
    return {}, HTTPStatus.OK
  save_command_runner.terminate()
  return {}, HTTPStatus.OK


@dispatch_bp.route("/disk-save-status.json")
@dispatch_bp.route("/disk-save-status")
def disk_save_status():
  return server._save_image.model.data

@dispatch_bp.route("/disk-load-status.json")
@dispatch_bp.route("/disk-load-status")
@dispatch_bp.route("/load/status")
def disk_load_status():
  tlog = get_triage_logger()
  tlog.debug(repr(server._load_image.model.data))
  return server._load_image.model.data


@dispatch_bp.route("/restore-types.json")
@dispatch_bp.route("/restore-types")
def route_restore_types():
  """Returning supported restore types."""
  # disk image type is in lib/disk_images
  return { "restoreTypes": read_disk_image_types() }


@dispatch_bp.route("/disks.json")
@dispatch_bp.route("/disks")
def route_disks():
  """Handles getting the list of disks"""
  server.disk_portal.detect_disks()
  disks = [jsoned_disk(disk) for disk in server.disk_portal.disks]
  tlog = get_triage_logger()
  tlog.debug(str(disks))
  return {"diskPages": 1, "disks": disks}


@dispatch_bp.route("/opticaldrives.json")
@dispatch_bp.route("/opticaldrives")
def route_optical_drives():
  """Handles getting the list of disks"""
  opticals = [jsoned_optical(optical) for optical in server.opticals]
  tlog = get_triage_logger()
  tlog.debug(repr(opticals))
  return {"opticaldrives": opticals}


@dispatch_bp.route("/disk-images.json")
@dispatch_bp.route("/disk-images")
def route_disk_images():
  """Handles getting the list of disk images on local media"""
  # Loading doesn't have to come from http server, but this is a good test for now.
  disk_images = server.disk_image_file_path
  if os.path.exists(disk_images):
    return send_file(disk_images, "application/json")
  return {"sources": server.disk_images }


@dispatch_bp.route("/load", methods=["POST"])
def route_load_image():
  # Disk image
  if not request.args.get('source'):
    return "No disk image selected", HTTPStatus.BAD_REQUEST

  newhostname = request.args.get("newhostname")
  imagefile = request.args.get("source")
  image_size = request.args.get("size") # This comes back in bytes from sending sources with size. value in query is always string.
  restore_type = request.args.get("restoretype")
  wipe_request = request.args.get("wipe")

  target_disks = get_target_devices_from_request(request)
  if not target_disks:
    return "No disk selected", HTTPStatus.BAD_REQUEST

  load_command_runner = server.get_runner(runner_class=LoadCommandRunner)

  for devname in target_disks:
    load_command_runner.queue_load(devname, restore_type, imagefile, image_size, wipe_request, newhostname)
    pass
  return {}, HTTPStatus.OK


def sync_disk_images(sources, target_disks, clean: bool):
  """Disk image manipulation common for sync and clean"""
  if not target_disks:
    return "No disk selected", HTTPStatus.BAD_REQUEST

  sync_command_runner:SyncCommandRunner = server.get_runner(runner_class=SyncCommandRunner)
  sync_command_runner.queue_sync(sources, target_disks, clean=clean)
  return {}, HTTPStatus.OK


@dispatch_bp.route("/sync", methods=["POST"])
def route_sync_image():
  # Disk image
  source = request.args.get('source')
  sources = request.args.get('sources')
  if source is None and sources is None:
    return "No disk image selected", HTTPStatus.BAD_REQUEST

  if sources is None:
    sources = [source]
    pass
  else:
    sources = sources.split(',')
    pass

  target_disks = get_target_devices_from_request(request)
  return sync_disk_images(sources, target_disks, False)


@dispatch_bp.route("/sync-status.json")
@dispatch_bp.route("/sync-status")
@dispatch_bp.route("/sync/status")
def route_sync_status():
  return server._sync_image.model.data


@dispatch_bp.route("/clean", methods=["POST"])
def route_clean_image():
  """clean disk images from the target disks"""
  target_disks = get_target_devices_from_request(request)
  return sync_disk_images([], target_disks, True)


@dispatch_bp.route("/delete", methods=["POST"])
def route_delete_image():
  name = request.args.get("name")
  restoretype = request.args.get("restoretype")
  tlog = get_triage_logger()

  for disk_image in get_disk_images():
    if disk_image['name'] != name or disk_image['restoreType'] != restoretype:
      continue

    fullpath = disk_image['fullpath']
    try:
      tlog.debug("Delete '%s'" % fullpath)
      os.remove(fullpath)
      tlog.debug("Delete '%s' succeeded." % fullpath)
      return {}, HTTPStatus.OK
    except Exception as _exc:
      # FIXME: better response?
      msg = "Delete '%s' failed.\n%s" % (fullpath, traceback.format_exc())
      tlog.info(msg)
      return {}, HTTPStatus.BAD_REQUEST
    pass
  return {}, HTTPStatus.NOT_FOUND

@dispatch_bp.route("/rename", methods=["POST"])
def route_rename_image():
  name_from = request.args.get("from")
  name_to = request.args.get("to")
  restoretype = request.args.get("restoretype")
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
      return {}, HTTPStatus.NOT_FOUND
    except Exception as _exc:
      # FIXME: better response?
      tlog.info("RENAME failed - %s/%s." % (restoretype, name_from), exc_info=True)
      return {}, HTTPStatus.BAD_REQUEST
      pass
  return {}, HTTPStatus.OK

# FIXME: probably does not work
@dispatch_bp.route("/mount", methods=["POST"])
def route_mount_disk(request):
  """Mount disk"""
  portal = server.disk_portal
  portal.detect_disks()
  disks = portal.disks

  requested = request.args.get("deviceName")
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
        return {}, HTTPStatus.BAD_REQUEST
      pass
    pass
  return {}, HTTPStatus.OK

@dispatch_bp.route("/wipe", methods=["POST"])
def route_wipe_disks():
  devname = request.args.get("deviceName")
  devnames = request.args.get("deviceNames")
  if devnames:
    devices = devnames.split(',')
  elif devname:
    devices = [devname]
  else:
    return {}, HTTPStatus.BAD_REQUEST

  wipe_command_runner:WipeCommandRunner = server.get_runner(WipeCommandRunner)
  (result, code) = wipe_command_runner.queue_wipe(devices)
  return result, code


def stop_runner(runner_class):
  runner = server.get_runner(runner_class, create=False)
  if runner:
    runner.terminate()
    pass
  return {}

@dispatch_bp.route("/wipe/status")
def disk_wipe_status():
  #tlog = get_triage_logger()
  #tlog.debug(repr(server._load_image.model.data))
  #return server._load_image.model.data
  return server._wipe_disk.model.data


@dispatch_bp.route("/stop-load", methods=["POST"])
@dispatch_bp.route("/load/stop", methods=["POST"])
def route_stop_load_image():
  return stop_runner(LoadCommandRunner)


@dispatch_bp.route("/stop-save", methods=["POST"])
@dispatch_bp.route("/save/stop", methods=["POST"])
def route_stop_save_image():
  return stop_runner(SaveCommandRunner)

@dispatch_bp.route("/stop-wipe", methods=["POST"])
@dispatch_bp.route("/wipe/stop", methods=["POST"])
def route_stop_disk_wipe():
  return stop_runner(WipeCommandRunner)

@dispatch_bp.route("/stop-sync", methods=["POST"])
@dispatch_bp.route("/sync/stop", methods=["POST"])
def route_stop_sync():
  return stop_runner(SyncCommandRunner)


@dispatch_bp.route("/shutdown", methods=["POST"])
def route_shutdown():
  """shutdowns the computer."""
  shutdown_mode = request.args.get("mode", ["ignored"])
  if shutdown_mode == "poweroff":
    subprocess.run(['poweroff'])
  elif shutdown_mode == "reboot":
    subprocess.run(['reboot'])
  else:
    return {}, HTTPStatus.BAD_REQUEST
  return {}, HTTPStatus.OK


@dispatch_bp.route("/network-device-status.json")
@dispatch_bp.route("/network-device-status")
def route_network_device_status():
  """Network status"""
  netstat = []
  for netdev in _network.detect_net_devices():
    netstat.append({"device": netdev.device_name, "carrier": netdev.is_network_connected()})
    server.update_component_decision(
      {"component": "Network", "device": netdev.device_name},
      {"result": netdev.is_network_connected(),
       "message": "Connection detected." if netdev.is_network_connected() else "Not conntected."})
    pass
  return netstat, HTTPStatus.OK

@dispatch_bp.route("/unmount", methods=["POST"])
def route_unmount():
  devname = request.args.get("deviceName")
  devnames = request.args.get("deviceNames")
  if devnames:
    devices = devnames.split(',')
  elif devname:
    devices = [devname]
  else:
    return {}, HTTPStatus.BAD_REQUEST

  unmount_command_runner = server.get_runner(UnmountCommandRunner)
  (result, code) = unmount_command_runner.queue_save(devices)
  return result, code



dispatch_bp.add_url_rule("/opticaldrivetest", view_func=route_opticaldrivetest, methods=["POST"])
