""" 
The MIT License (MIT)
Copyright (c) 2019 - Naoyuki Tai

WCE Triage HTTP server - 
and webscoket server

"""

from wce_triage.version import *
import aiohttp
import aiohttp.web
from aiohttp.web_exceptions import *
import aiohttp_cors
from argparse import ArgumentParser
from collections import namedtuple
from contextlib import closing
import json
import os, sys, re, subprocess, datetime, asyncio, pathlib, traceback, queue, time, uuid
import logging, logging.handlers
import functools

from wce_triage.components.computer import Computer
from wce_triage.components.disk import Disk, Partition, DiskPortal
from wce_triage.lib.util import *
from wce_triage.lib.timeutil import *
from wce_triage.ops.ops_ui import ops_ui
from wce_triage.lib.pipereader import *
from wce_triage.components import optical_drive as _optical_drive
from wce_triage.components import sound as _sound
from wce_triage.lib.disk_images import *


tlog = get_triage_logger()
routes = aiohttp.web.RouteTableDef()
import socketio
wock = socketio.AsyncServer(async_mode='aiohttp', logger=get_triage_logger(), cors_allowed_origins='*')


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
def jsoned_disk(disk):
  return {"target": 0,
          "deviceName": disk.device_name,
          "runTime": 0,
          "runEstimate": 0,
          "mounted": disk.mounted,
          "size": round(disk.get_byte_size() / 1000000),
          "bus": "usb" if disk.is_usb else "ata",
          "model": disk.vendor + " " + disk.model_name }

def jsoned_optical(optical):
  return {"deviceName": optical.device_name,
          "model": optical.vendor + " " + optical.model_name }

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
    global me
    running = True
    while running:
      try:
        elem = Emitter.queue.get(block=False)
        tlog.debug("EMITTER: sending %d: '%s' '%s'" % (elem[0], elem[1], elem[2]))
        await wock.emit(elem[1], elem[2])

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

  # This is to send message
  def note(message):
    Emitter._send('message', {"message": message})
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

  def __init__(self, app, rootdir, cors, loop, live_triage):
    """
    HTTP request handler for triage
    """
    self.live_triage = live_triage
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
    self.messages = []
    self.triage_timestamp = None

    self.loading_status = { "pages": 1, "steps": [] }
    # wock (web socket) channels.
    self.channels = {}

    self.pipe_readers = {}

    self.restore = None
    self.imaging = None
    self.optests = []

    self.wock = wock

    self.disk_portal = DiskPortal()

    asyncio.ensure_future(TriageWeb._periodic_update(), loop=loop)
    pass

  #
  async def _periodic_update():
    global me
    while True:
      await asyncio.sleep(0.5)
      if me.triage_timestamp is None:
        continue

      computer = me.computer
      (added, changed, removed) = me.disk_portal.detect_disks()
      
      if added or changed or removed:
        disks = [ jsoned_disk(disk) for disk in me.disk_portal.disks ]
        Emitter._send('diskupdate', disks)
        pass

      for component in computer.components:
        for update_key, update_value in component.detect_changes():
          updated = computer.update_decision( update_key,
                                              update_value,
                                              overall_changed=me.overall_changed)
          if updated:
            # join the key and value and send it
            update_value.update(update_key)
            Emitter._send('triageupdate', update_value)
          pass
        pass
      pass
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
  # 
  # FIXME: Running process is not coroutine! I am learning that, things that can be
  # coroutine is not coroutine at all, like time.sleep, subprocess.*.
  # Waiting on process is blocking.
  # I think what's needed is to run a triage (which isn't too slow) in a loop from
  # service and pick off the result.
  async def triage(self):
    if self.triage_timestamp is None:
      self.triage_timestamp = datetime.datetime.now()
      computer = Computer()
      self.overall_decision = computer.triage(live_system=self.live_triage)
      tlog.info("Triage is done.")
      self.computer = computer
      pass
    return self.computer

  @routes.get("/dispatch/triage.json")
  async def route_triage(request):
    """Handles requesting triage result"""
    global me
    hello = me.computer == None
    await me.triage()
    computer = me.computer

    decisions = [ { "component": "Overall", "result": me.overall_decision } ] + computer.decisions
    jsonified = { "components":  decisions }

    if hello:
      Emitter.note("Hello from Triage service Version " + TRIAGE_VERSION)
      pass

    return aiohttp.web.json_response(jsonified)

  # Updating the overall decision
  def overall_changed(self, new_decision):
    self.overall_decision = new_decision
    Emitter._send('triageupdate', { "component": "Overall", "result": new_decision })
    pass

  @routes.get("/dispatch/disks.json")
  async def route_disks(request):
    """Handles getting the list of disks"""
    global me
    me.disk_portal.detect_disks()
    
    disks = [ jsoned_disk(disk) for disk in me.disk_portal.disks ]
    tlog.debug(str(disks))
    jsonified = { "diskPages": 1, "disks": disks }
    return aiohttp.web.json_response(jsonified)


  @routes.get("/dispatch/disk.json")
  async def route_disk(request):
    """Disk detail info"""
    global me

    # If triage is not done, it's temporarly unavailable
    if me.computer is None:
      raise HTTPServiceUnavailable()

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
    global me
    while me.computer is None:
      await me.triage()
      pass

    music_file = None
    for asset in os.listdir(TriageWeb.asset_path):
      if asset.endswith(".mp3"):
        music_file = os.path.join(TriageWeb.asset_path, asset)
        break
      pass

    if music_file:
      resp = aiohttp.web.FileResponse(music_file)
      resp.content_type="audio/mpeg"

      updated = None
      if _sound.detect_sound_device():
        computer = me.computer
        updated = computer.update_decision( {"component": "Sound" },
                                            {"result": True,
                                             "message": "Sound is tested." },
                                            overall_changed=me.overall_changed)
        pass
      return resp
    
    Emitter.note(message)
    raise HTTPNotFound()


  @routes.get("/dispatch/opticaldrives.json")
  async def route_opticaldrives(request):
    """Handles getting the list of disks"""
    global me
    while me.computer is None:
      await me.triage()
      pass
    
    reply = [ jsoned_optical(optical) for disk in computer.opticals._drives ]
    jsonified = { "opticaldrives": reply }
    return aiohttp.web.json_response(jsonified)

  @routes.post("/dispatch/opticaldrivetest")
  async def route_opticaldrive(request):
    """Test optical drive"""
    global me

    while me.computer is None:
      await me.triage()
      pass

    computer = me.computer
    opticals = computer.opticals

    if opticals.count() == 0:
      tlog.debug('No optical drives detected.')
      raise HTTPNotFound()

    # Since reading optical is slow, the answer goes back over websocket.
    for optical in opticals._drives:
      # await me.wock.emit("opticaldrive", { "device": optical.device_name })
      # restore image runs its own course, and output will be monitored by a call back
      tlog.debug("run wce_triage.bin.test_optical " + optical.device_name)
      optical_test = subprocess.Popen( ['python3', '-m', 'wce_triage.bin.test_optical', optical.device_name],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      asyncio.get_event_loop().add_reader(optical_test.stdout, functools.partial(me.watch_optest, optical_test.stdout))
      asyncio.get_event_loop().add_reader(optical_test.stderr, functools.partial(me.watch_optest, optical_test.stderr))
      me.optests.append((optical_test, optical.device_name))
      pass
    return aiohttp.web.json_response({})


  def check_optest_process(self):
    if self.optests:
      optests = self.optests[:]
      for optest in optests:
        # FIXME:
        # I think I need to check the process active in better way.
        process, device_name = optest
        process.poll()
        if process.returncode:
          self.optests.remove(optest)
          returncode = process.returncode
          if returncode == 0:
            Emitter.note("Optical drive test succeeded.")
            pass
          else:
            Emitter.note("Optical drive test failed with error code %d" % returncode)
            pass
          pass
        pass
      pass
    pass


  def watch_optest(self, pipe):
    reader = self.pipe_readers.get(pipe)
    if reader is None:
      reader = PipeReader(pipe)
      self.pipe_readers[pipe] = reader
      pass

    line = reader.readline()
    if line == b'':
      tlog.debug("FromOptest: optical test stream ended.")
      asyncio.get_event_loop().remove_reader(pipe)
      del self.pipe_readers[pipe]
      pass
    elif line is not None:
      tlog.debug("FromOptest: '%s'" % line)
      try:
        packet = json.loads(line)
        message = packet['message']

        computer = me.computer
        updated = None
        if computer:
          updated = computer.update_decision( {"component": "Optical drive",
                                               "device": message['device'] },
                                              { "result": message['result'],
                                                "message": message['message'],
                                                "verdict": message['verdict'] },
                                              overall_changed=me.overall_changed)
          pass

        payload = packet['message']
        if updated:
          payload['message'] = updated.message
          pass
        # packet['event'] == 'triageupdate'
        Emitter._send('triageupdate', payload)
      except Exception as exc:
        tlog.info("FromOptest: '%s'" % line)
        pass
      pass

    self.check_optest_process()
    pass


  @routes.get("/dispatch/network-device-status.json")
  async def route_network_device_status(request):
    """Network status"""
    global me
    await me.triage()
    computer = me.computer

    netstat = []
    for netdev in detect_net_devices():
      netstat.append( { "device": netdev.device_name, "carrier": netdev.is_network_connected() } )
      updated = computer.update_decision( {"component": "Network",
                                           "device": netdev.device_name},
                                          { "result": netdev.is_network_connected(),
                                            "message": "Connection detected." if netdev.is_network_connected() else "Not conntected."},
                                          overall_changed=me.overall_changed)
      pass
    return aiohttp.web.json_response({ "network": netstat })


  @routes.get("/dispatch/disk-images.json")
  async def route_disk_images(request):
    """Handles getting the list of disk images on local media"""

    # Loading doesn't have to come from http server, but this is
    # a good test for now.
    disk_images = '/usr/local/share/wce/wce-disk-images/wce-disk-images.json'
    if os.path.exists(disk_images):
      resp = aiohttp.web.FileResponse(disk_images)
      resp.content_type="application/json"
      return resp
    return aiohttp.web.json_response({ "sources": get_disk_images() })


  @routes.get("/remote-disk-images.json")
  async def route_disk_images(request):
    """Returning the disk image for remote loading.
       This is probably not going to be used for serving installation payload.
       It should be done by the http server like lighttpd
    """
    peeraddr, myaddr = get_ip_addresses()
    myport = arguments.port

    sources = []
    url_template = 'http://{myaddr}:{myport}/wce-disk-images/{restoretype}/{filename}'
    for source in get_disk_images():
      source['fullpath'] = url_template.format(myaddr=myaddr, myport=myport, restoretype=source.restoretype, filename=source.name)
      sources.append(source)
      pass
    return aiohttp.web.json_response({ "sources": sources })


  # Restore types
  #  content - content loading for disk
  #  triage - USB stick flashing
  #  clone - cloning 
  #  
  @routes.get("/dispatch/restore-types.json")
  async def route_restore_types(request):
    """Returning supported restore types."""
    # disk image type is in lib/disk_images
    return aiohttp.web.json_response({ "restoreTypes": read_disk_image_types() })

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
    
    await me.wock.emit("loadimage", { "device": devname, "runStatus": "", "totalEstimate" : 0, "steps" : [] })
    if not imagefile:
      Emitter.note("No image file selected.")
      await Emitter.flush()
      return aiohttp.web.json_response({})

    # restore image runs its own course, and output will be monitored by a call back
    me.restore = subprocess.Popen( ['python3', '-m', 'wce_triage.ops.restore_image_runner', devname, imagefile, imagefile_size, newhostname, restore_type],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    asyncio.get_event_loop().add_reader(me.restore.stdout, functools.partial(me.restore_progress_report, me.restore.stdout))
    asyncio.get_event_loop().add_reader(me.restore.stderr, functools.partial(me.restore_progress_report, me.restore.stderr))
    return aiohttp.web.json_response({})


  def check_restore_process(self):
    if self.restore:
      self.restore.poll()
      if self.restore.returncode:
        returncode = self.restore.returncode
        self.restore = None
        if returncode is not 0:
          Emitter.note("Restore failed with error code %d" % returncode)
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
        Emitter.note(line)
        pass
      pass

    self.check_restore_process()
    pass


  @routes.post("/dispatch/stop-load")
  async def route_stop_load_image(request):
    global me
    if me.restore and me.restore.returncode is None:
      me.restore.kill()
      pass
    return aiohttp.web.json_response({})


  @routes.get("/dispatch/disk-load-status.json")
  async def route_disk_load_status(request):
    """Load disk image to disk"""
    global me
    return aiohttp.web.json_response(me.loading_status)


  @routes.get("/dispatch/disk-save-status.json")
  async def route_disk_save_status(request):
    """Create and save disk image"""
    # FIXME: Implement!
    return aiohttp.web.json_response({})


  @routes.get("/dispatch/download")
  async def route_download_image(request):
    """Download disk image. not implemented yet."""
    return aiohttp.web.json_response({})


  @routes.post("/dispatch/save")
  async def route_save_image(request):
    """Create disk image and save"""
    global me
    devname = request.query.get("deviceName")
    imagefile = request.query.get("destination")

    await me.wock.emit("saveimage", { "device": devname, "runStatus": "", "totalEstimate" : 0, "steps" : [] })

    # restore image runs its own course, and output will be monitored by a call back
    me.restore = subprocess.Popen( ['python3', '-m', 'wce_triage.ops.create_image_runner', devname, imagefile, imagefile_size, newhostname, restore_type],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    asyncio.get_event_loop().add_reader(me.restore.stdout, functools.partial(me.restore_progress_report, me.restore.stdout))
    asyncio.get_event_loop().add_reader(me.restore.stderr, functools.partial(me.restore_progress_report, me.restore.stderr))
    return aiohttp.web.json_response({})


  def check_restore_process(self):
    if self.restore:
      self.restore.poll()
      if self.restore.returncode:
        returncode = self.restore.returncode
        self.restore = None
        if returncode is not 0:
          Emitter.note("Restore failed with error code %d" % returncode)
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
        Emitter.note(line)
        pass
      pass

    self.check_restore_process()
    pass


  @routes.post("/dispatch/mount")
  async def route_mount_disk(request):
    """Mount disk"""
    global me
    me.disk_portal.detect_disks()
    disks = me.disk_portal.disks

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
          Emitter.note(exc.format_exc())
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
      Emitter.note("Power off")
      subprocess.run(['poweroff'])
    elif shutdown_mode == "reboot":
      Emitter.note("Reboot")
      subprocess.run(['reboot'])
    else:
      Emitter.note("Shutdown command needs a query and ?mode=poweroff or ?mode=reboot is accepted.")
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
cli.add_argument("--live-triage", type=str, metavar="ROOTDIR", dest="live_triage", default=False)
arguments = cli.parse_args()

# If the module is invoked directly, initialize the application
if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO,
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                      filename='/tmp/triage.log')
  tlog = get_triage_logger()
  tlog.setLevel(logging.DEBUG)
  
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
  cors = aiohttp_cors.setup(app)
  wock.attach(app)
  global me
  me = TriageWeb(app, arguments.rootdir, cors, loop, arguments.live_triage)

  tlog.info("Starting server, use <Ctrl-C> to stop...")
  tlog.info(u"Open {0} in a web browser.".format(the_root_url))
  Emitter.register(loop)

  aiohttp.web.run_app(app, host="0.0.0.0", port=arguments.port, access_log=get_triage_logger())
  pass
