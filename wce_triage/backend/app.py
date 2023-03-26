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
import click
from flask.cli import CertParamType, _validate_key, SeparatedPathType, pass_script_info, show_server_banner, get_debug_flag
from werkzeug.serving import run_simple


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

# Define and parse the command line arguments
def create_app():
  from ..lib.util import set_triage_logger
  ui_dir = os.path.join(os.path.split((os.path.split(__file__)[0]))[0], "ui")
  app = Flask(__name__, root_path=ui_dir)
  set_triage_logger(app.logger, filename="/tmp/triage.log", log_level=logging.DEBUG)
  app.url_map.strict_slashes = False

  @app.cli.command('wce')
  @click.option("--wcedir")
  @click.option("--rootdir")
  @click.option("--wce_share")
  @click.option("--live-triage")
  @click.option("--host", "-h", default="127.0.0.1", help="The interface to bind to.")
  @click.option("--port", "-p", default=5000, help="The port to bind to.")
  @click.option(
    "--cert", type=CertParamType(), help="Specify a certificate file to use HTTPS."
  )
  @click.option(
    "--key",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    callback=_validate_key,
    expose_value=False,
    help="The key file to use when specifying a certificate.",
  )
  @click.option(
    "--reload/--no-reload",
    default=None,
    help="Enable or disable the reloader. By default the reloader "
         "is active if debug is enabled.",
  )
  @click.option(
    "--debugger/--no-debugger",
    default=None,
    help="Enable or disable the debugger. By default the debugger "
         "is active if debug is enabled.",
  )
  @click.option(
    "--eager-loading/--lazy-loading",
    default=None,
    help="Enable or disable eager loading. By default eager "
         "loading is enabled if the reloader is disabled.",
  )
  @click.option(
    "--with-threads/--without-threads",
    default=True,
    help="Enable or disable multithreading.",
  )
  @click.option(
    "--extra-files",
    default=None,
    type=SeparatedPathType(),
    help=(
      "Extra files that trigger a reload on change. Multiple paths"
      f" are separated by {os.path.pathsep!r}."
    ),
  )
  @pass_script_info
  def cli_wce(info, wcedir, rootdir, wce_share, live_triage,
    host, port, reload, debugger, eager_loading, with_threads, cert, extra_files):
    from .cli import DevConfig
    if wcedir:
      DevConfig.WCEDIR = wcedir
    if rootdir:
      DevConfig.TRIAGE_UI_ROOTDIR = rootdir
    if wce_share:
      DevConfig.WCE_SHARE_URL = wce_share
    if live_triage:
      DevConfig.LIVE_TRIAGE = live_triage in ["yes", "true", "on"]
    from .server import server
    app.config.from_object(DevConfig)
    server.set_app(app, socketio, DevConfig)

    debug = get_debug_flag()

    if reload is None:
        reload = debug

    if debugger is None:
        debugger = debug

    show_server_banner(debug, info.app_import_path)
    run_simple(
        host,
        port,
        info.load_app,
        use_reloader=reload,
        use_debugger=debugger,
        threaded=with_threads,
        ssl_context=cert,
        extra_files=extra_files
    )
    pass

  CORS(app)
  socketio = SocketIO(app, cors_allowed_origins="*", engineio_logger=False, logger=False)
  init_socketio(app, socketio)
  from .meta_bp import meta_bp
  app.register_blueprint(meta_bp)

  from .dispatch_bp import dispatch_bp
  app.register_blueprint(dispatch_bp)

  from .wce_bp import wce_bp
  app.register_blueprint(wce_bp)

  return app
