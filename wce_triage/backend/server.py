"""
The MIT License (MIT)
Copyright (c) 2019 - Naoyuki Tai

WCE Triage HTTP server -
and webscoket server

"""
import sys
from argparse import ArgumentParser
import os, re
# import logging, logging.handlers
import subprocess
import json
import traceback

from ..lib.disk_images import get_disk_images
from ..const import const
from ..lib.util import get_triage_logger, init_triage_logger
from flask import Flask

init_triage_logger(filename="/tmp/server.log")
tlog = get_triage_logger()
from .app_instance import init_app

# Define and parse the command line arguments
import socket

cli = ArgumentParser(description='Triage web server')
# Port for this HTTP server
cli.add_argument("-p", "--port", type=int, metavar="PORT", dest="port", default=8400)

# And it's hostname. It's usually the local host FQDN but, as the client's DNS may not work reliably,
# you need to be able to set this sometimes.
cli.add_argument("--host", type=str, metavar="HOST", dest="host", default=socket.getfqdn())

# Location of UI assets.
cli.add_argument("--rootdir", type=str, metavar="WCE_TRIAGE_UI_ROOTDIR", dest="rootdir", default=None)

# This is where disk images live
cli.add_argument("--wcedir", type=str, metavar="WCE_ROOT_DIR", dest="wcedir", default="/usr/local/share/wce")

# If you want to use other server (any other http server) you need to override this.
# This is necessary if you want to offload the payload download to web server light apache.
# For this case, you need to be able to use any URL.
# Note that, the boot arg (aka cmdline) is used for picking up the default value of wce_share_url
# as well, and this overrides this.
cli.add_argument("--wce_share", type=str, metavar="WCE_SHARE_URL", dest="wce_share", default=None)

cli.add_argument("--live-triage", dest="live_triage", action='store_true')
arguments = cli.parse_args(sys.argv[2:])

wce_share_re = re.compile(const.wce_share + '=([\w\/\.+\-_\:\?\=@#\*&\\%]+)')
wce_payload_re = re.compile(const.wce_payload + '=([\w\.+\-_\:\?\=@#\*&\\%]+)')

class TriageServer(Flask):

  def __init__(self, import_name, **kwargs):
    self.cpu_info = None
    self.benchmark = None
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

    super().__init__(import_name, root_path=self.rootdir, **kwargs)
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

    (app, self.socketio) = init_app(self)
    from dispatch_view import
    pass

  def get_cpu_info(self):
    if self.cpu_info is None:
      tlog.debug("get_cpu_info: starting")
      self.cpu_info = subprocess.Popen("python3 -m wce_triage.lib.cpu_info", shell=True, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
      tlog.debug("get_cpu_info: started")
      (out, err) = self.cpu_info.communicate()
      tlog.debug("get_cpu_info: ended")
      try:
        self.benchmark = json.loads(out)
      except:
        tlog.info("watch_cpu_info - json.loads: '%s'\n%s" % (out, traceback.format_exc()))
        pass
      pass
    return self.benchmark

  pass

tlog.info("Starting app.")
app = TriageServer('wce-triage')
