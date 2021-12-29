from flask_classful import FlaskView, route
from flask import send_from_directory

class WceView(FlaskView):

  def get(self, path):  # /usr/local/share/wce
    return send_from_directory("/usr/local/share/wce", path)
