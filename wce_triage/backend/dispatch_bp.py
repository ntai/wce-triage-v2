import os

from .save_command import SaveCommandRunner
from ..lib.disk_images import read_disk_image_types
from ..lib.util import get_triage_logger
from flask import jsonify, send_file, send_from_directory, Blueprint, request
from ..components import sound as _sound
from .server import server
from http import HTTPStatus

tlog = get_triage_logger()

WIPE_TYPES = [{"id": "nowipe", "name": "No Wipe", "arg": ""},
              {"id": "wipe", "name": "Full wipe", "arg": "-w"},
              {"id": "shortwipe", "name": "Wipe first 1Mb", "arg": "--quickwipe"}]

dispatch_bp = Blueprint('dispatch', __name__, url_prefix='/dispatch')

# id: ID used for front/back communication
# name: displayed on web
# arg: arg used for restore image runner.
@dispatch_bp.route("/wipe-types.json")
def route_wipe_types():
  """Returning wipe types."""
  return jsonify({"wipeTypes": WIPE_TYPES})

#
#
@dispatch_bp.route("/triage.json")
def route_triage():
  """Handles requesting triage result"""
  return jsonify({"components": server.triage})


@dispatch_bp.route("/music")
def route_music():
  """Send mp3 stream to chrome"""
  # For now, return the first mp3 file. Triage usually has only one
  # mp3 file for space reason.
  if server.computer is None:
    server.triage()
    pass

  music_file = None
  asset_path = server.asset_path
  for asset in os.listdir(asset_path):
    if asset.endswith(".ogg"):
      music_file = os.path.join(asset_path, asset)
      break
    pass

  if music_file:
    res = send_file(music_file, mimetype="audio/" + music_file[-3:])

    if _sound.detect_sound_device():
      computer = server.computer
      updated = computer.update_decision({"component": "Sound"},
                                         {"result": True,
                                          "message": "Sound is tested."},
                                         overall_changed=server.overall_changed)
      # FIXME: Do something meaningful, like send a wock message.
      if updated:
        tlog.info("updated")
        pass
      pass
    return res
  return {}, HTTPStatus.NOT_FOUND


@dispatch_bp.route("/messages")
def route_messages():
  return jsonify(server.messages)

#
# TriageWeb
#
@dispatch_bp.route('/wce/<path:path>')
def ulswce(path):  # /usr/local/share/wce
  return send_from_directory(server.wcedir, path)


# get_cpu_info is potentially ver slow for older computers as this runs a
# cpu benchmark.

@dispatch_bp.route("/cpu_info.json")
def route_cpu_info():
  """Handles getting CPU rating """
  return jsonify(server.cpu_info.data)


@dispatch_bp.route("/save", methods=["POST"])
def save_disk_image():
  devname = request.args.get("deviceName")
  saveType = request.args.get("type")
  destdir = request.args.get("destination")
  partid = request.args.get("partition", default="Linux")
  runner_name = "save"
  save_command_runner = server.get_runner(runner_name)
  if save_command_runner is None:
    save_command_runner = SaveCommandRunner()
    server.set_runner(runner_name, save_command_runner)
    pass
  (result, code) = save_command_runner.queue_save(devname, saveType, destdir, partid)
  return result, code


@dispatch_bp.route("/stop-save", methods=["POST"])
def stop_save():
  runner_name = "save"
  save_command_runner = server.get_runner(runner_name)
  if save_command_runner is None:
    return {}, HTTPStatus.OK
  save_command_runner.terminate()
  return {}, HTTPStatus.OK


@dispatch_bp.get("/disk-save-status.json")
def disk_save_status():
  return jsonify(server.save_model)

@dispatch_bp.get("/restore-types.json")
def route_restore_types():
  """Returning supported restore types."""
  # disk image type is in lib/disk_images
  return jsonify({ "restoreTypes": read_disk_image_types() })
