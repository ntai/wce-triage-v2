"""
The MIT License (MIT)
Copyright (c) 2022 - Naoyuki Tai

WCE Triage HTTP server -
and webscoket server

"""
import logging

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
import os

from wce_triage.backend.config import Config


def init_socketio(app: Flask, socketio: SocketIO):
    @socketio.on('connect')
    def connect():
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


def create_app(wcedir=None, rootdir=None, wce_share=None, live_triage=False, payload=None):
  from ..lib.util import set_triage_logger
  ui_dir = os.path.join(os.path.split((os.path.split(__file__)[0]))[0], "ui")
  app = Flask(__name__, root_path=ui_dir)
  set_triage_logger(app.logger, log_level=logging.DEBUG)
  app.url_map.strict_slashes = False

  Config.cmdline()

  from .config import DevConfig
  if wcedir:
    DevConfig.WCEDIR = wcedir
  if rootdir:
    DevConfig.TRIAGE_UI_ROOTDIR = rootdir
  if wce_share:
    DevConfig.WCE_SHARE_URL = wce_share
  if live_triage:
    DevConfig.LIVE_TRIAGE = live_triage
  if payload and (not live_triage):
    DevConfig.PAYLOAD = payload

  Config.check_auto_load()
  app.config.from_object(DevConfig)

  CORS(app)
  socketio = SocketIO(app, cors_allowed_origins="*", engineio_logger=False, logger=False)
  init_socketio(app, socketio)
  from .meta_bp import meta_bp
  app.register_blueprint(meta_bp)

  from .dispatch_bp import dispatch_bp
  app.register_blueprint(dispatch_bp)

  from .wce_bp import wce_bp
  app.register_blueprint(wce_bp)

  from .server import server
  server.set_app(app, socketio, DevConfig)

  return app
