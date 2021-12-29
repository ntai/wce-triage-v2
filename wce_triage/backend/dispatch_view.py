import os
from ..lib.util import get_triage_logger
from flask import jsonify, send_file, send_from_directory
from .server import app
from ..components import sound as _sound

tlog = get_triage_logger()

WIPE_TYPES = [{"id": "nowipe", "name": "No Wipe", "arg": ""},
              {"id": "wipe", "name": "Full wipe", "arg": "-w"},
              {"id": "shortwipe", "name": "Wipe first 1Mb", "arg": "--quickwipe"}]

# id: ID used for front/back communication
# name: displayed on web
# arg: arg used for restore image runner.
@app.route("/dispatch/wipe-types.json")
def route_wipe_types():
    """Returning wipe types."""
    return jsonify({"wipeTypes": WIPE_TYPES})

#
#
@app.route("/dispatch/triage.json")
def route_triage():
    """Handles requesting triage result"""
    computer = app.triage()

    decisions = [{"component": "Overall", "result": app.overall_decision}] + computer.decisions
    jsonified = {"components": decisions}
    return jsonify(jsonified)


@app.route("/music")
def route_music():
    """Send mp3 stream to chrome"""
    # For now, return the first mp3 file. Triage usually has only one
    # mp3 file for space reason.
    if app.computer is None:
        app.triage()
        pass

    music_file = None
    asset_path = app.asset_path
    for asset in os.listdir(asset_path):
        if asset.endswith(".ogg"):
            music_file = os.path.join(asset_path, asset)
            break
        pass

    if music_file:
        res = send_file(music_file, mimetype="audio/" + music_file[-3:])

        if _sound.detect_sound_device():
            computer = app.computer
            updated = computer.update_decision({"component": "Sound"},
                                               {"result": True,
                                                "message": "Sound is tested."},
                                               overall_changed=app.overall_changed)
            # FIXME: Do something meaningful, like send a wock message.
            if updated:
                tlog.info("updated")
                pass
            pass
        return res
    return {}, 404


@app.route("/messages")
@app.route("/dispatch/messages")
def route_messages():
    return jsonify({"messages": app.messages})

#
# TriageWeb
#
@app.route('/wce/<path:path>')
def ulswce(path):  # /usr/local/share/wce
    return send_from_directory(app.wcedir, path)

@app.route("/dispatch/triage.json")
def route_triage():
    """Handles requesting triage result"""
    computer = app.triage()
    decisions = [{"component": "Overall", "result": app.overall_decision}] + computer.decisions
    return jsonify({"components": decisions})

# get_cpu_info is potentially ver slow for older computers as this runs a
# cpu benchmark.

@app.route("/dispatch/cpu_info.json")
def route_cpu_info():
    """Handles getting CPU rating """
    return jsonify({"cpu_info": app.get_cpu_info()})

