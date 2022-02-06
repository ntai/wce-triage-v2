"""
The MIT License (MIT)
Copyright (c) 2022 - Naoyuki Tai

WCE Triage HTTP server -
and webscoket server

"""
import logging

from ..lib.util import get_triage_logger, init_triage_logger
from flask import Flask, send_file
from flask_cors import CORS
from flask_socketio import SocketIO
init_triage_logger(filename="/tmp/server.log", log_level=logging.DEBUG)
tlog = get_triage_logger()
import os


def init_socketio(socketio: SocketIO):
    @socketio.on('connect')
    def connect(auth):
        wockid = "foo"
        #me.channels[wockid] = environ
        tlog.debug("WOCK: %s connected" % wockid)
        return None

    @socketio.on('message')
    def message(data):
        wockid = "foo"
        tlog.debug("WOCK: %s incoming %s" % (wockid, data))
        return None

    @socketio.on('disconnect')
    def disconnect():
        wockid = "foo"
        tlog.debug("WOCK: %s disconnect" % (wockid))
        return None

    pass


# Define and parse the command line arguments
def init_app():
  from .server import server
  ui_dir = os.path.join(os.path.split((os.path.split(__file__)[0]))[0], "ui")
  app = Flask(__name__, root_path=ui_dir)
  app.config['SECRET_KEY'] = 'notsecret'
  CORS(app)
  socketio = SocketIO(app, cors_allowed_origins="*")
  init_socketio(socketio)
  from .meta_bp import meta_bp
  app.register_blueprint(meta_bp)

  from .dispatch_bp import dispatch_bp
  app.register_blueprint(dispatch_bp)

  server.set_app(app, socketio)
  return app

app = init_app()
