""" 
The MIT License (MIT)
Copyright (c) 2019 - Naoyuki Tai

WCE Triage HTTP server - 
and webscoket server

"""
import aiohttp
import aiohttp.web
import aiohttp_cors
from argparse import ArgumentParser
from collections import namedtuple
from contextlib import closing
import json
import os, sys, re, subprocess, datetime, asyncio, pathlib, traceback, queue, time, uuid
import logging, logging.handlers
import functools

from wce_triage.components.computer import Computer
from wce_triage.ops.restore_image_runner import RestoreDiskRunner
from wce_triage.ops.create_image_runner import ImageDiskRunner
from wce_triage.components.disk import Disk, Partition
import wce_triage.lib.util
from wce_triage.lib.timeutil import *
from wce_triage.ops.ops_ui import ops_ui
from wce_triage.ops.partition_runner import make_usb_stick_partition_plan, make_efi_partition_plan
from wce_triage.lib.pipereader import *

routes = aiohttp.web.RouteTableDef()

import socketio
wock = socketio.AsyncServer(async_mode='aiohttp', logger=True, cors_allowed_origins='*')

#
import logging
tlog = logging.getLogger('triage')


@routes.get('/version.json')
async def route_version(request):
  """Get the version number of backend"""

  wce_triage_parent_dir = None
  for pa in sys.path:
    p_wce_triage = os.path.join(pa, "wce_triage")
    if os.path.exists(p_wce_triage) and os.path.isdir(p_wce_triage):
      wce_triage_parent_dir = pa
      break
    pass

  # hack alert
  dist_info_re = re.compile(r'wce_triage-(\d+\.\d+.\d+).dist-info')
    
  version = "Unknown"
  for adir in os.listdir(wce_triage_parent_dir):
    matched = dist_info_re.match(adir)
    if matched:
      version = matched.group(1)
      break
    pass

  # FIXME: Front end version is in manifest.
  fversion = "0.0.1"
  jsonified = { "version": [ {"backend": version },  {"frontend": fversion } ] }
  return aiohttp.web.json_response(jsonified)

#
#
#
class Emitter:
  queue = None
  item_count = 0

  def register(loop):
    Emitter.queue = queue.Queue()
    asyncio.ensure_future(Emitter._task(), loop=loop)
    pass

  async def _task():
    while True:
      await Emitter.flush()
      await asyncio.sleep(0.2)
      pass
    pass

  async def flush():
    running = True
    while running:
      try:
        elem = Emitter.queue.get(block=False)
        tlog.debug("EMITTER: sending %d  %s" % (elem[0], elem[1]))
        await wock.emit(elem[1], elem[2])

        global me
        # so when browser asks with "get", I can answer the same
        # result.
        if elem[1] == "loadimage":
          me.loading_status = elem[2]
          pass
        pass
      except queue.Empty:
        running = False
        pass
      pass
    pass


  def _send(event, data):
    tlog.debug("EMITTER: queueing %d  %s" % (Emitter.item_count, event))
    Emitter.queue.put((Emitter.item_count, event, data))
    Emitter.item_count += 1
    pass
  pass


#
# TriageWeb
#
# NOTE: Unfortunately, aiohttp dispatch doesn't give me "self", so only alternative
# is to use a singleton. IOW, this class is nothing more than a namespace.
#
class TriageWeb(object):
  asset_path = "/usr/local/share/wce/triage/assets"

  def __init__(self, app, rootdir, cors):
    """
    HTTP request handler for triage
    """
    app.router.add_routes(routes)
    app.router.add_static("/", rootdir)
    for resource in app.router._resources:
      if resource.raw_match("/socket.io/"):
        continue
      try:
        cors.add(resource, { '*': aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*") })
      except Exception as exc:
        pass
      pass

    self.computer = None
    self.messages = ['WCE Triage Version 0.0.1']
    self.triage_timestamp = None

    self.loading_status = { "pages": 1, "steps": [] }
    # wock (web socket) channels.
    self.channels = {}

    self.pipe_readers = {}
    pass

  def note(self, message):
    Emitter._send('message', {"message": message})
    pass


  @routes.get("/")
  async def route_root(request):
    raise aiohttp.web.HTTPFound('/index.html')
    return None

  @routes.get("/dispatch/messages")
  async def route_messages(request):
    global me
    return aiohttp.web.json_response({ "messages": me.messages })


  # triage being async is somewhat pedantic but it runs a couple of processes
  # so it's slow enough.
  async def triage(self):
    current_time = datetime.datetime.now()
    if self.triage_timestamp and in_seconds(current_time - self.triage_timestamp) > 5:
      self.triage_timestamp = None
      pass
    if self.triage_timestamp is None:
      self.computer = Computer()
      self.overall_decision = self.computer.triage()
      self.triage_timestamp = current_time
      self.note("Triage result is %s." % "good" if self.overall_decision else "bad")
      await Emitter.flush()
      pass
    return self.computer


  @routes.get("/dispatch/triage.json")
  async def route_triage(request):
    """Handles requesting triage result"""
    global me
    await me.triage()
    computer = me.computer

    decisions = [ { "component": "Overall", "result": "Good" if me.overall_decision else "Bad" } ] + [ {"component": thing, "result": "Good" if good else "Bad", "details": dtl} for thing, good, dtl in computer.decisions ]
    # decision comes back as tuple, make it to the props for jsonify
    jsonified = { "components":  decisions }
    return aiohttp.web.json_response(jsonified)


  @routes.get("/dispatch/disks.json")
  async def route_disks(request):
    """Handles getting the list of disks"""

    global me
    if me.computer is None:
      await me.triage()
      pass
    computer = me.computer
    computer.detect_disks()
    
    disks = [ {"target": 0,
               "deviceName": disk.device_name,
               "runTime": 0,
               "runEstimate": 0,
               "mounted": "y" if disk.mounted else "n",
               "size": round(disk.get_byte_size() / 1000000),
               "bus": "usb" if disk.is_usb else "ata",
               "model": disk.vendor + " " + disk.model_name }
              for disk in computer.disks ]

    jsonified = { "diskPages": 1, "disks": disks }
    return aiohttp.web.json_response(jsonified)


  @routes.get("/dispatch/disk.json")
  async def route_disk(request):
    """Disk detail info"""
    global me
    if me.computer is None:
      await me.triage()
      pass
    computer = me.computer
    disk_info = computer.hw_info.find_entry("storage", {"logicalname" : device_name})
    if disk_info:
      return aiohttp.web.json_response(disk_info)
    return aiohttp.web.json_response({})
    

  @routes.get("/dispatch/music")
  async def route_music(request):
    """Send mp3 stream to chrome"""
    # For now, return the first mp3 file. Triage usually has only one
    # mp3 file for space reason.
    
    music_file = None
    for asset in os.listdir(TriageWeb.asset_path):
      if asset.endswith(".mp3"):
        music_file = os.path.join(TriageWeb.asset_path, asset)
        break
      pass

    if music_file:
      resp = aiohttp.web.FileResponse(music_file)
      resp.content_type="audio/mpeg"
      return resp
    raise HTTPNotFound()


  @routes.get("/dispatch/network-device-status.json")
  async def route_network_device_status(request):
    """Network status"""
    
    netstat = []
    for netdev in detect_net_devices():
      netstat.append( { "device": netdev.device_name, "carrier": netdev.is_network_connected() } )
      pass
    return aiohttp.web.json_response({ "network": netstat })


  @routes.get("/dispatch/disk-images.json")
  async def route_disk_images(request):
    """Handles getting the list of disk images"""
    return aiohttp.web.json_response({ "sources": wce_triage.lib.util.get_disk_images() })


  # Restore types
  #  content - content loading for disk
  #  triage - USB stick flashing
  #  clone - cloning 
  @routes.get("/dispatch/restore-types.json")
  async def route_restore_types(request):
    """Returning supported restore types."""
    return aiohttp.web.json_response({ "restoreTypes": [{ "id": "wce",
                                                          "name" : "WCE content loading"},
                                                        { "id" : "triage",
                                                          "name" : "Triage USB flash drive" },
                                                        { "id" : "clone",
                                                          "name": "Disk restore" } ] })

  @routes.post("/dispatch/load")
  async def route_load_image(request):
    """Load disk image to disk"""
    global me
    devname = request.query.get("deviceName")
    imagefile = request.query.get("source")
    imagefile_size = request.query.get("size") # This comes back in bytes from sending sources with size. value in query is always string.
    newhostname = request.query.get("newhostname")
    restore_type = request.query.get("restoretype")

    if newhostname is None:
      newhostname = {'triage': 'wcetriage2', 'wce': 'wce' + uuid.uuid4().hex[:8]}.get(restore_type, 'host' + uuid.uuid4().hex[:8])
      pass
    
    await wock.emit("loadimage", { "device": devname, "totalEstimate" : 0, "steps" : [] })
    if not imagefile:
      me.note("No image file selected.")
      await Emitter.flush()
      return aiohttp.web.json_response({ "pages": 1 })

    # restore image runs its own course, and output will be monitored by a call back
    me.restore = subprocess.Popen( ['python3', '-m', 'wce_triage.ops.restore_image_runner', devname, imagefile, imagefile_size, newhostname, restore_type],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    asyncio.get_event_loop().add_reader(me.restore.stdout, functools.partial(me.restore_progress_report, me.restore.stdout))
    asyncio.get_event_loop().add_reader(me.restore.stderr, functools.partial(me.restore_progress_report, me.restore.stderr))
    return aiohttp.web.json_response({ "pages": 1 })


  def check_restore_process(self):
    if self.restore:
      self.restore.poll()
      if self.restore.returncode:
        returncode = self.restore.returncode
        self.restore = None
        if returncode is not 0:
          self.note("Restore failed with error code %d" % returncode)
          pass
        pass
      pass
    pass

  def restore_progress_report(self, pipe):
    reader = self.pipe_readers.get(pipe)
    if reader is None:
      reader = PipeReader(pipe)
      self.pipe_readers[pipe] = reader
      pass

    line = reader.readline()
    if line == b'':
      asyncio.get_event_loop().remove_reader(pipe)
      del self.pipe_readers[pipe]
      pass
    elif line is not None:
      tlog.debug("FromRestore: '%s'" % line)
      if self.restore and pipe == self.restore.stdout:
        # This is a message from loader
        try:
          packet = json.loads(line)
          Emitter._send(packet['event'], packet['message'])
        except Exception as exc:
          tlog.info("FromRestore: BAD LINE '%s'" % line)
          pass
        pass
      else:
        self.note(line)
        pass
      pass

    self.check_restore_process()
    pass


  @routes.get("/dispatch/disk-load-status.json")
  async def route_disk_load_status(request):
    """Load disk image to disk"""
    global me
    return aiohttp.web.json_response(me.loading_status)

  @routes.post("/dispatch/save")
  async def route_save_image(request):
    """Create disk image ans save"""
    # FIXME: needs actual implementation
    return aiohttp.web.json_response({})

  @routes.post("/dispatch/mount")
  async def route_mount_disk(request):
    """Mount disk"""
    global me
    disks=me.triage().detect_disks()

    requested = requst.query.get("deviceName")
    for disk in disks:
      if disk.device_name in requested:
        try:
          mount_point = disk.device_name.get_mount_point()
          if not os.path.exists(mount_point):
            os.mkdir(mount_point)
            pass
          subprocess.run(["mount", disk.device_name, mount_point])
          pass
        except Exception as exc:
          me.note(exc.format_exc())
          await Emitter.flush()
          pass
        pass
      pass
    return aiohttp.web.json_response(fake_status)

  @routes.post("/dispatch/unmount")
  async def route_unmount_disk(request):
    """Unmount disk"""
    disks = requst.query.get("deviceName")
    for disk in disks:
      subprocess.run(["umount", disk])
      pass
    return aiohttp.web.json_response(fake_status)


  @routes.post("/dispatch/shutdown")
  async def route_shutdown(request):
    """shutdowns the computer."""
    global me
    shutdown_mode = request.query.get("mode", ["ignored"])
    if shutdown_mode == "poweroff":
      me.note("Power off")
      subprocess.run(['poweroff'])
    elif shutdown_mode == "reboot":
      me.note("Reboot")
      subprocess.run(['reboot'])
    else:
      me.note("Shutdown command needs a query and ?mode=poweroff or ?mode=reboot is accepted.")
      await Emitter.flush()
      raise HTTPNotFound()
      pass
    return aiohttp.web.json_response({})
  
  pass
  
@wock.event
async def connect(wockid, environ):
  global me
  me.channels[wockid] = environ
  tlog.debug("WOCK: %s connected" % wockid)
  me.note("Hello from Triage service.")
  await Emitter.flush()
  pass


@wock.event()
async def message(wockid, data):
  tlog.debug("WOCK: %s incoming %s" % (wockid, data))
  pass

@wock.event
def disconnect(wockid):
  global me
  if me.channels.get(wockid):
    del me.channels[wockid]
    tlog.debug("WOCK: %s disconnect" % (wockid))
    pass
  else:
    tlog.debug("WOCK: %s disconnect from stranger" % (wockid))
    pass
  pass

# Define and parse the command line arguments
import socket
cli = ArgumentParser(description='Example Python Application')
cli.add_argument("-p", "--port", type=int, metavar="PORT", dest="port", default=8312)
cli.add_argument("--host", type=str, metavar="HOST", dest="host", default=socket.getfqdn())
cli.add_argument("--rootdir", type=str, metavar="ROOTDIR", dest="rootdir", default="/usr/local/share/wce/wce-triage-ui")
arguments = cli.parse_args()

# If the module is invoked directly, initialize the application
if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)

  fileout = logging.FileHandler("/tmp/triage.log")
  for logkind in ['triage', 'aiohttp.access', 'aiohttp.internal', 'aiohttp.server', 'aiohttp.web']:
    lgr = logging.getLogger(logkind)
    lgr.setLevel(logging.DEBUG)
    lgr.addHandler(fileout)
    pass
  
  # Create and configure the HTTP server instance
  the_root_url = u"{0}://{1}:{2}{3}".format("HTTP",
                                            arguments.host,
                                            arguments.port,
                                            "/index.html")
  loop = asyncio.get_event_loop()
  # loop.set_debug(True)

  # Accept connection from everywhere
  tlog.info("Starting app.")
  app = aiohttp.web.Application(debug=True, loop=loop)
  wock.attach(app)
  cors = aiohttp_cors.setup(app)
  global me
  me = TriageWeb(app, arguments.rootdir, cors)


  tlog.info("Starting server, use <Ctrl-C> to stop...")
  tlog.info(u"Open {0} in a web browser.".format(the_root_url))
  Emitter.register(loop)
  aiohttp.web.run_app(app, host="0.0.0.0", port=arguments.port)
  pass
