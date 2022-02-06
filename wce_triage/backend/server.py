"""
The MIT License (MIT)
Copyright (c) 2022 - Naoyuki Tai

server data storage

"""
import os, re
import time
from typing import Optional
from flask import Flask
from flask_socketio import SocketIO

from .messages import UserMessages
from .models import Model, ModelDispatch
from .cpu_info import CpuInfoModel
from .process_runner import ProcessRunner
from .save_command import SaveModelDispatch
from .view import View
from ..components.disk import DiskPortal
from ..components.computer import Computer
from ..lib.disk_images import get_disk_images
from ..const import const
from ..lib.util import get_triage_logger
import itertools
import datetime
import threading
import typing

wce_share_re = re.compile(const.wce_share + '=([\w/.+\-_:?=@#*&\\%]+)')
wce_payload_re = re.compile(const.wce_payload + '=([\w.+\-_:?=@#*&\\%]+)')

tlog = get_triage_logger()


class DiskModel(Model):
  disk_portal: DiskPortal

  def __init__(self):
    super().__init__(meta={"tag": "disks"})
    self.disk_portal = DiskPortal()
    pass

  def refresh_disks(self):
    self.set_model_data(self.disk_portal.decision())
    pass

  pass


class TriageServer(threading.Thread):
  app: Flask
  socketio: SocketIO
  _disks: ModelDispatch
  _loading: ModelDispatch
  _save_model: ModelDispatch
  _cpu_info: CpuInfoModel
  _disk_portal: Optional[DiskPortal]
  _emit_counter: itertools.count
  _runners: dict
  _computer: Optional[Computer]
  triage_timestamp: Optional[datetime.datetime]
  live_triage: bool
  overall_decision: list

  def __init__(self):
    super().__init__()
    from .cli import arguments

    self.tlog = get_triage_logger()

    self._disks = ModelDispatch(DiskModel(), view=self._socketio_view)
    self._load_image = ModelDispatch(Model(meta={"tag": "loadimage"}), view=self._socketio_view)
    self._save_image = SaveModelDispatch(Model(meta={"tag": "saveimage"}), view=self._socketio_view)
    self._wipe_disk = ModelDispatch(Model(meta={"tag": "wipe"}), view=self._socketio_view)

    self._cpu_info = CpuInfoModel()
    self._disk_portal = None
    self.autoload = False
    self.load_disk_options = None
    self.wcedir = arguments.wcedir
    self._emit_counter = itertools.count()
    self._runners = {}
    self._computer = None
    self.triage_timestamp = None
    self._socketio_view = SocketIOView()

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
    self.live_triage = arguments.live_triage

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
    UserMessages.set_view(MessageSocketIOView())
    self.start()
    pass

  def run(self):
    count = 0
    while True:
      time.sleep(1)
      self.priodic_taks()

      count += 1
      if count % 10 == 0:
        UserMessages.note("Hello {}".format(count))
        pass
      pass
    pass

  def priodic_taks(self):
    if self.triage_timestamp is None:
      return

    computer = self._computer
    (added, changed, removed) = self.disk_portal.detect_disks()

    if added or changed or removed:
      disks = {"disks": [jsoned_disk(disk) for disk in me.disk_portal.disks]}
      self._disks.set_model_data(disks)
      # Emitter._send('diskupdate', disks)
      pass

    for component in computer.components:
      for update_key, update_value in component.detect_changes():
        updated = computer.update_decision(update_key,
                                           update_value,
                                           overall_changed=me.overall_changed)
        if updated:
          # join the key and value and send it
          update_value.update(update_key)
          Emitter._send('triageupdate', update_value)
        pass
      pass

    # Kick off the content loading if all of criterias look good
    if me.autoload:
      me.autoload = False
      me.target_disks = []

      for disk in me.disk_portal.disks:
        disk_gb = disk.get_byte_size() / 1000000000
        if (not disk.mounted) and (disk_gb >= 80):
          me.target_disks.append(disk.device_name)
          pass
        pass

      # If the machine has only one disk and not mounted, autload can start
      # otherwise, don't start.
      if len(me.target_disks) == 1:
        me.start_load_disks("AUTOLOAD:")
        pass
      else:
        me.target_disks = []
        pass
      pass
    pass

  @property
  def cpu_info(self):
    return self._cpu_info

  @property
  def save_model(self) -> Model:
    return self._save_model

  @property
  def disk_portal(self) -> DiskPortal:
    if self._disk_portal:
      self._disk_portal = DiskPortal()
      pass
    return self._disk_portal

  @property
  def emit_count(self) -> int:
    # a bit of a hack but convenient
    return next(self._emit_counter)

  def set_runner(self, name: str, runner: ProcessRunner) -> None:
    self._runners[name] = runner
    pass

  def get_runner(self, name: str) -> Optional[ProcessRunner]:
    return self._runners.get(name)

  def send_to_ui(self, event: str, message: dict):
    if not isinstance(message, dict):
      raise Exception("message is not dict.")
    message['_sequence_'] = self.emit_count
    self.socketio.emit(event, message)
    pass

  @property
  def triage(self) -> list:
    if self.triage_timestamp is None:
      self.triage_timestamp = datetime.datetime.now()
      if self._computer is None:
        self._computer = Computer()
        pass
      self.overall_decision = self._computer.triage(live_system=self.live_triage)
      pass
    decisions = [ { "component": "Overall", "result": self.overall_decision } ] + self._computer.decisions
    return decisions

  pass


class SocketIOView(View):
  def __init__(self):
    pass

  def updating(self, t0: dict, update: typing.Optional[any], meta):
    server.send_to_ui(meta.get("tag", "message"), update)
    pass
  pass


class MessageSocketIOView(View):
  event: str
  def __init__(self, event):
    self.event = event
    pass

  def updating(self, t0: dict, update: typing.Optional[any]):
    server.send_to_ui(self.event, update)
    pass
  pass


server = TriageServer()
