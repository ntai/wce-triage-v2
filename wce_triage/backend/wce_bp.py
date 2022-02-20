from flask import send_from_directory, Blueprint
from .server import server

wce_bp = Blueprint('wce', __name__, url_prefix='/wce')

@wce_bp.route('/<path:path>')
def ulswce(path):  # /usr/local/share/wce
  return send_from_directory(server.wcedir, path)
