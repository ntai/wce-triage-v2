"""
The MIT License (MIT)
Copyright (c) 2022 - Naoyuki Tai

WCE Triage HTTP server -
and webscoket server

"""
import os, re

from flask import Flask
from flask_socketio import SocketIO

from .models import Model, DiskModel

from .cpu_info import CpuInfoModel

from ..lib.disk_images import get_disk_images
from ..const import const
from ..lib.util import get_triage_logger, init_triage_logger

wce_share_re = re.compile(const.wce_share + '=([\w\/\.+\-_\:\?\=@#\*&\\%]+)')
wce_payload_re = re.compile(const.wce_payload + '=([\w\.+\-_\:\?\=@#\*&\\%]+)')

tlog = get_triage_logger()

class TriageServer(object):
  _benchmark: Model
  _triage: Model
  _disks: DiskModel
  _loading: Model
  _saving: Model
  _messages: Model
  _cpu_info: CpuInfoModel

  def __init__(self):
    from .cli import arguments

    self.tlog = get_triage_logger()
    self._benchmark = Model()
    self._triage = Model()
    self._disks = DiskModel()
    self._loading = Model()
    self._saving = Model()
    self._messages = Model()
    self._cpu_info = CpuInfoModel()

    self.autoload = False
    self.load_disk_options = None

    self.wcedir = arguments.wcedir

    # static files are here
    self.rootdir = arguments.rootdir
    if self.rootdir is None:
      self.rootdir = os.path.join(self.wcedir, "wce-triage-ui")
      pass

    self.the_root_url = u"{0}://{1}:{2}".format("http", arguments.host, arguments.port)

    if arguments.wce_share:
      self.wce_share_url = arguments.wce_share
    else:
      self.wce_share_url = u"{0}://{1}:{2}/wce".format("http", arguments.host, arguments.port)
      pass

    self.asset_path = os.path.join(self.wcedir, "triage", "assets")

    self.wce_payload = None

    with open("/proc/cmdline") as cmdlinefd:
      cmdline = cmdlinefd.read()
      match = wce_share_re.search(cmdline)
      if match:
        self.wce_share_url = match.group(1)
        pass
      if not arguments.live_triage:
        match = wce_payload_re.search(cmdline)
        if match:
          self.wce_payload = match.group(1)
          pass
        pass
      pass

    if self.wce_payload:
      disk_image = None
      for disk_image in get_disk_images(self.wce_share_url):
        if disk_image['name'] == self.wce_payload:
          self.autoload = True
          break
        pass

      if self.autoload:
        self.load_disk_options = disk_image
        # translate the load option lingo here and web side
        # this could be unnecessary if I change the UI to match the both world
        self.load_disk_options['source'] = disk_image['fullpath']
        self.load_disk_options['restoretype'] = disk_image['restoreType']
        # size from get_disk_images comes back int, and web returns string.
        # going with string.
        self.load_disk_options['size'] = str(disk_image['size'])
        pass
      else:
        tlog.info("Payload {0} is requested but not autoloading as matching disk image does not exist.".format(
          self.wce_payload))
        self.wce_payload = None
        pass
      pass
    tlog.info(u"Open {0}{1} in a web browser. WCE share is {2}".format(self.the_root_url, "/index.html", self.wce_share_url))
    pass

  def set_app(self, app: Flask, socketio: SocketIO):
    self.app = app
    self.socketio = socketio
    pass

  pass

server = TriageServer()
