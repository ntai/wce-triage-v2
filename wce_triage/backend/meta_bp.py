import traceback
# from ..lib.util import get_triage_logger
from flask import jsonify, send_file, send_from_directory, Blueprint
from ..version import TRIAGE_VERSION, TRIAGE_TIMESTAMP
import json

meta_bp = Blueprint('meta', __name__, static_folder="/ui")

@meta_bp.route("/")
@meta_bp.route("/index.html")
def root_index():
  return send_file("index.html")


@meta_bp.route('/version.json')
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
