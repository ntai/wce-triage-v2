import traceback
from flask import jsonify, send_file, Blueprint
from ..version import TRIAGE_VERSION, TRIAGE_TIMESTAMP
import json
import os
from .config import DevConfig

ui_dir = DevConfig.TRIAGE_UI_ROOTDIR
if not ui_dir or not os.path.exists(ui_dir):
  ui_dir = "/ui"
  pass

meta_bp = Blueprint('meta', __name__, static_folder=ui_dir)

@meta_bp.route("/")
@meta_bp.route("/index.html")
def root_index():
  return send_file("index.html")


@meta_bp.route('/favicon.ico')
def favicon():
  return send_file("favicon.ico", mimetype='image/vnd.microsoft.icon')


@meta_bp.route('/version.json')
@meta_bp.route('/version')
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
  except Exception as _exc:
    from ..lib import get_triage_logger, init_triage_logger
    tlog = get_triage_logger()
    tlog.info(
      'Reading /usr/local/share/wce/wce-triage-ui/manifest.json failed with exception. ' + traceback.format_exc())
    pass
  jsonified = {"version": {"backend": TRIAGE_VERSION + "-" + TRIAGE_TIMESTAMP, "frontend": fversion}}
  return jsonify(jsonified)

