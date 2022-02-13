"""
The MIT License (MIT)
Copyright (c) 2022 - Naoyuki Tai

WCE Triage HTTP server -
and webscoket server

"""
import logging

from flask import Flask, send_file
from flask_cors import CORS
from flask_socketio import SocketIO
import os

def init_socketio(socketio: SocketIO):
    @socketio.on('connect')
    def connect(auth):
        wockid = "foo"
        #me.channels[wockid] = environ
        app.logger.debug("WOCK: %s connected" % wockid)
        return None

    @socketio.on('message')
    def message(data):
        wockid = "foo"
        app.logger.debug("WOCK: %s incoming %s" % (wockid, data))
        return None

    @socketio.on('disconnect')
    def disconnect():
        wockid = "foo"
        app.logger.debug("WOCK: %s disconnect" % (wockid))
        return None

    pass


# Define and parse the command line arguments
def init_app():
  from ..lib.util import set_triage_logger
  ui_dir = os.path.join(os.path.split((os.path.split(__file__)[0]))[0], "ui")
  app = Flask(__name__, root_path=ui_dir)
  set_triage_logger(app.logger, filename="/tmp/triage.log", log_level=logging.DEBUG)
  app.config['SECRET_KEY'] = 'notsecret'
  app.config['PROPAGATE_EXCEPTIONS'] = False
  CORS(app)
  socketio = SocketIO(app, cors_allowed_origins="*")
  init_socketio(socketio)
  from .meta_bp import meta_bp
  app.register_blueprint(meta_bp)

  from .dispatch_bp import dispatch_bp
  app.register_blueprint(dispatch_bp)

  from .server import server
  server.set_app(app, socketio)
  return app

app = init_app()
