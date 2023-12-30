"""
The MIT License (MIT)
Copyright (c) 2022 - Naoyuki Tai

server data storage

"""
import logging
import os, re
import time
from typing import Optional
from flask import Flask
from flask_socketio import SocketIO

from .config import Config
from .formatters import jsoned_disk
from .messages import UserMessages, ErrorMessages
from .models import Model, ModelDispatch
from .cpu_info import CpuInfoModel
from .process_runner import ProcessRunner, RunnerOutputDispatch, ImageRunnerOutputDispatch
from .view import View
from ..components import DiskPortal
from ..components import Computer
from ..components import OpticalDrives
from ..lib.disk_images import get_disk_images
from ..const import const
from ..lib import get_triage_logger
import itertools
import datetime
import threading
import typing
import subprocess
import json
import traceback

wce_share_re = re.compile(const.wce_share + r'=([\w/.+\-_:?=@#*&\\%]+)')
wce_payload_re = re.compile(const.wce_payload + r'=([\w.+\-_:?=@#*&\\%]+)')

class TriageServer(threading.Thread):
  app: Flask
  config: Config
  socketio: SocketIO
  _disks: ModelDispatch
  _loading: ModelDispatch
  _save_image: ModelDispatch
  _load_image: ModelDispatch
  _wipe_disk: ModelDispatch
  _sync_image: ModelDispatch
  _cpu_info: ModelDispatch
  _disk_portal: Optional[DiskPortal]
  _emit_counter: itertools.count
  _runners: dict
  _computer: Optional[Computer]
  _triage: ModelDispatch
  triage_timestamp: Optional[datetime.datetime]
  overall_decision: list
  target_disks: list
  dispatches : dict
  locks: dict

  def __init__(self):
    super().__init__()

    self.tlog = get_triage_logger()
    self._socketio_view = SocketIOView()
    self._disks = ModelDispatch(DiskModel(default = {"disks": []}), view=self._socketio_view)

    self._load_image = ImageRunnerOutputDispatch(Model(default={"pages": 1, "tasks": [], "diskRestroing": False, "device": ""}, meta={"tag": "loadimage"}), view=self._socketio_view)
    self._save_image = ImageRunnerOutputDispatch(Model(default={"pages": 1, "tasks": [], "diskSaving": False, "device": ""}, meta={"tag": "saveimage"}), view=self._socketio_view)
    self._wipe_disk = RunnerOutputDispatch(Model(default={"pages": 1, "tasks": [], "diskWiping": False, "device": ""}, meta={"tag": "wipe"}), view=self._socketio_view)
    self._sync_image = RunnerOutputDispatch(Model(default={"pages": 1, "tasks": [], "device": ""}, meta={"tag": "diskimage"}), view=self._socketio_view)

    self.dispatches = {"load": (self._load_image, None),
                       "save": (self._save_image, None),
                       "wipe": (self._wipe_disk, None),
                       "sync": (self._sync_image, None)}

    self._cpu_info = ModelDispatch(CpuInfoModel())
    self._disk_portal = None
    self.autoload = False
    self.load_disk_options = None
    self._emit_counter = itertools.count()
    self._runners = {}
    self._computer = None
    self._triage = ModelDispatch(Model(meta={"tag": "triage"}, default=[]), view=self._socketio_view)
    self.triage_timestamp = None
    self.target_disks = []
    self.locks = {}
    for lock_name in ["cpu_info"] :
      self.locks[lock_name] = threading.Lock()
      pass
    pass


  def setup(self, config: Config):
    self.config = config

    payload = self.config.PAYLOAD
    if payload:
      disk_image = None
      for disk_image in get_disk_images(self.config.WCE_SHARE_URL):
        if disk_image['name'] == payload:
          break
        pass

      self.autoload = not self.config.LIVE_TRIAGE
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
        self.tlog.info("Payload {0} is requested but not autoloading as matching disk image does not exist.".format(
          payload))
        self.autoload = False
        pass
      pass
    pass

  def set_app(self, app: Flask, socketio: SocketIO, config):
    self.app = app
    self.socketio = socketio
    message_socketio_view = MessageSocketIOView("message")
    logging_view = LoggingView(self.tlog)
    view = MultiView(views=[message_socketio_view, logging_view])
    UserMessages.set_view(view)
    ErrorMessages.set_view(view)

    self.setup(config)
    self.start()
    pass

  def get_lock(self, lock_name) -> threading.Lock:
    return self.locks.get(lock_name)

  def run(self):
    while True:
      self.periodic_task()
      time.sleep(2)
      pass
    pass

  def overall_changed(self, new_decision):
    """When the overall decision is changed, update the triage decisions and set it to the triage."""
    self.overall_decision = new_decision
    self._triage.dispatch(self.triage_decisions)
    pass


  def check_autoload(self):
    """Kick off the content loading if all of criterias look good"""
    if self.autoload:
      self.autoload = False
      self.target_disks = []

      for disk in self.disk_portal.disks:
        disk_gb = disk.get_byte_size() / 1000000000
        if (not disk.mounted) and (disk_gb >= 80):
          self.target_disks.append(disk.device_name)
          pass
        pass

      # If the machine has only one disk and not mounted, autload can start
      # otherwise, don't start.
      if len(self.target_disks) == 1:
        self.start_load_disks("AUTOLOAD:")
        pass
      else:
        self.target_disks = []
        pass
      pass
    pass

  def periodic_task(self):
    if self.triage_timestamp is None:
      self.initial_triage()
      pass
    self.update_triage()
    self.check_autoload()
    pass

  @property
  def cpu_info_killer(self):
    lock = self.get_lock("cpu_info")
    lock.acquire()
    try:
      if self._cpu_info.model.model_state is None:
        out = None
        try:
          self.tlog.debug("get_cpu_info: starting")
          cpu_info = subprocess.Popen("python3 -m wce_triage.lib.cpu_info", shell=True, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
          self.tlog.debug("get_cpu_info: started")
          (out, err) = cpu_info.communicate()
          self.tlog.debug("get_cpu_info: done")
        except Exception as exc:
          self.tlog.debug("something happened")
          pass

        if out:
          try:
            self._cpu_info.dispatch(json.loads(out))
          except Exception as exc:
            self.tlog.info("get_cpu_info - json.loads: '%s'\n%s" % (out, traceback.format_exc()))
            self._cpu_info.model.set_model_state(False)
            pass
          pass
        pass
      pass
    finally:
      lock.release()
      pass
    return self._cpu_info.model.data

  @property
  def cpu_info(self):
    lock = self.get_lock("cpu_info")
    lock.acquire()
    try:
      if self._cpu_info.model.model_state is None:
        self._cpu_info.model.set_model_state(False)
        from .simple_process import CpuInfoCommandRunner
        cpu_info = CpuInfoCommandRunner(self._cpu_info)
        cpu_info.start()
        pass
      pass
    finally:
      lock.release()
      pass
    if self._cpu_info.model.model_state is True:
      return self._cpu_info.model.data, 200
    return {}, 202

  @property
  def disk_portal(self) -> DiskPortal:
    if self._disk_portal is None:
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

  def get_runner(self, runner_class:ProcessRunner=None, create=True,
                 stdout_dispatch=None, stderr_dispatch=None, meta=None) -> Optional[ProcessRunner]:
    runner_class = ProcessRunner if runner_class is None else runner_class
    name = runner_class.class_name()
    runner = self._runners.get(name)
    if runner is None and create:
      out, err = self.dispatches.get(name)
      if stdout_dispatch:
        out = stdout_dispatch
        pass
      if stderr_dispatch:
        err = stderr_dispatch
        pass
      runner = runner_class(stdout_dispatch=out, stderr_dispatch=err, meta=meta)
      self.register_runner(runner)
      runner.start()
      pass
    return runner

  def register_runner(self, runner):
    name = runner.__class__.class_name()
    self._runners[name] = runner
    pass

  def send_to_ui(self, event: str, message: dict):
    if isinstance(message, dict):
      message['_sequence_'] = self.emit_count
      pass
    self.socketio.emit(event, message)
    pass

  @property
  def triage_decisions(self) -> list:
    if self.triage_timestamp is None:
      self.update_triage()
      pass
    decisions = [ { "component": "Overall", "result": self.overall_decision } ] + self._computer.decisions
    return decisions


  def initial_triage(self):
    self.triage_timestamp = datetime.datetime.now()
    self._computer = Computer()
    self.overall_changed(self._computer.triage(live_system=self.config.LIVE_TRIAGE))
    pass


  def update_triage(self):
    computer: Computer = self._computer
    (added, changed, removed) = self.disk_portal.detect_disks()

    disks = {"disks": [jsoned_disk(disk) for disk in self.disk_portal.disks]}
    if len(self._disks.model.data["disks"]) != len(disks["disks"]) or max(
      [0 if t0 == t1 else 1 for t0, t1 in zip(disks["disks"], self._disks.model.data["disks"])]) == 1:
      self._disks.dispatch(disks)
      pass

    for component in computer.components:
      for desc, updates in component.detect_changes():
        self.update_component_decision(desc, updates)
        pass
      pass
    pass

  def update_component_decision(self, descriptors: dict, updates: dict):
    """keys dict : descriptor of component. (eg: { "component": "ethernet", "device": "eth0" })
updates dict : values to update (eg: { "verdict": True, "message": "Network is working" })
overall_changed:

When a status/decision of component changes, this is called to update the decision of component which may or may not change the overall decision as well.

Since there is no way to listen to audio, only way to confirm the functionality of component is to listen to the sound played on the computer.
A triaging person can decide whether not sound playing. Also, if you plug in Ethernet to a router, the network status changes (such as detecting carrier) so it's done through this.
    """
    computer: Computer  = self._computer
    updated = computer.update_decision(descriptors, updates, overall_changed=self.overall_changed)
    if updated:
      # join the key and value and send it
      updates.update(descriptors)
      self._triage.dispatch(updates)
      pass
    pass


  @property
  def triage(self) -> list:
    return self._triage.model.data

  @property
  def disk_images(self) -> list:
    return get_disk_images(wce_share_url=self.config.WCE_SHARE_URL)

  @property
  def disk_image_file_path(self) -> str:
      return os.path.join(self.config.WCEDIR, "wce-disk-images", "wce-disk-images.json")

  @property
  def opticals(self) -> OpticalDrives:
    _ = self.triage_decisions
    return self._computer.opticals


  def start_load_disks(self, reason):
    # FIXME
    pass

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

  def updating(self, t0: dict, update: typing.Optional[any], meta):
    if not isinstance(update, dict):
      raise Exception("message must be a dict")
    if not update.get("message"):
      raise Exception("message must have the 'message' key")
    server.send_to_ui(self.event, update)
    pass
  pass



class DiskModel(Model):
  def __init__(self, **kwargs):
    super().__init__(meta={"tag": "disks"}, **kwargs)
    pass

  def refresh_disks(self):
    self.set_model_data(server.disk_portal.decision())
    pass

  pass


class LoggingView(View):
  logger: logging.Logger

  def __init__(self, logger):
    self.logger = logger
    pass

  def updating(self, t0: dict, update: typing.Optional[any], meta):
    level = meta.get("level", logging.INFO)
    self.logger.log(level, update)
    pass
  pass


class MultiView(View):
  def __init__(self, *args, views=None, **kwargs):
    self.views = views if views else []
    super().__init__(*args, **kwargs)
    pass

  def add_view(self, view):
    self.views.append(view)
    pass

  def updating(self, t0: dict, update: typing.Optional[any], meta):
    for view in self.views:
      view.updating(t0, update, meta)
      pass
    pass

  def updated(self, t1: dict, meta: dict):
    for view in self.views:
      view.updated(t1, meta)
      pass
    pass
  pass

server = TriageServer()
