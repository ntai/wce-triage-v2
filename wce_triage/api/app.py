import os
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import json
import traceback

from .emitter import start_emitter_thread
from ..lib import get_triage_logger

environ = os.environ
wcedir = environ.get("wcedir")
rootdir = environ.get("rootdir")
wce_share = environ.get("wce_share")
live_triage = environ.get("live_triage", False)
payload = environ.get("payload")
ui_dir = os.path.join(os.path.split((os.path.split(__file__)[0]))[0], "ui")

# Create a FastAPI instance
app = FastAPI(docs_url="/docs")
app.mount("/wce", StaticFiles(directory=wcedir), name="wce")

from .config import DevConfig

app.add_middleware(
  CORSMiddleware,
  allow_origins=DevConfig.CORS_ORIGIN_WHITELIST,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)
# Create a SocketIO instance
# Note: 'async_mode' could be 'asgi' or 'aiohttp' depending on your preference
sockio = socketio.AsyncServer(async_mode='asgi',
                              cors_allowed_origins=DevConfig.CORS_ORIGIN_WHITELIST,
                              cors_allowed_methods=["*"],
                              cors_credentials=True,  # Allow credentials
                              )
socket_app = socketio.ASGIApp(sockio, other_asgi_app=app)

from ..version import TRIAGE_VERSION, TRIAGE_TIMESTAMP

emit_queue = start_emitter_thread(sockio)

from .server import server



server.set_config(emit_queue, DevConfig)

@app.get('/version')
def route_version() -> JSONResponse:
  """Get the version number of backend"""
  # FIXME: Front end version is in manifest.
  fversion = "1.0.0"
  try:
    with open('/usr/local/share/wce/wce-triage-ui/manifest.json') as frontend_manifest:
      manifest = json.load(frontend_manifest)
      fversion = manifest.get('version', "1.0.0")
      pass
    pass
  except Exception as _exc:
    from ..lib import get_triage_logger, get_triage_logger
    tlog = get_triage_logger()
    tlog.info(
      'Reading /usr/local/share/wce/wce-triage-ui/manifest.json failed with exception. ' + traceback.format_exc())
    pass
  jsonified = {"version": {"backend": TRIAGE_VERSION + "-" + TRIAGE_TIMESTAMP, "frontend": fversion}}
  return JSONResponse(jsonified)

@app.get('/hello')
def route_hello() -> JSONResponse:
  """Get the version number of backend"""
  # FIXME: Front end version is in manifest.
  return JSONResponse({"message": "world"})

from .routers.dispatch import router as dispatch_router
app.include_router(dispatch_router, prefix='/dispatch')

@sockio.event
def connect(sid, _environ):
  get_triage_logger().debug("connect ", sid)


# UI static must be the last
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
