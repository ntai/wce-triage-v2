from flask import Flask, send_file, jsonify
from flask_cors import CORS
import json
import traceback

from .emitter import init_socketio
from ..version import TRIAGE_VERSION, TRIAGE_TIMESTAMP
from flask_socketio import SocketIO


def init_app(app, **kwargs):

    @app.route("/")
    @app.route("/index.html")
    def root_index():
        return send_file("index.html")

    @app.route('/version.json')
    def route_version():
        """Get the version number of backend"""
        # FIXME: Front end version is in manifest.
        fversion = "1.0.0"
        try:
            with open('/usr/local/share/wce/wce-triage-ui/manifest.json') as frontend_manifest:
                manifest = json.load(frontend_manifest)
                fversion = manifest.get('version', "1.0.0")
                pass
            pass
        except Exception as exc:
            from ..lib.util import get_triage_logger, init_triage_logger
            tlog = get_triage_logger()
            tlog.info(
                'Reading /usr/local/share/wce/wce-triage-ui/manifest.json failed with exception. ' + traceback.format_exc())
            pass
        jsonified = {"version": {"backend": TRIAGE_VERSION + "-" + TRIAGE_TIMESTAMP, "frontend": fversion}}
        return jsonify(jsonified)

    CORS(app)
    socketio = SocketIO(app, cors_allowed_origins="*")
    init_socketio(socketio)
    return (app, socketio)
