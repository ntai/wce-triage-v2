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
from json import dumps
import os, sys, re, subprocess, datetime, asyncio, pathlib, traceback
import logging, logging.handlers
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from wce_triage.components.computer import Computer
from wce_triage.ops.restore_image_runner import RestoreDisk
from wce_triage.ops.create_image_runner import ImageDisk
from wce_triage.components.disk import Disk, Partition
from wce_triage.ops.restore_image_runner import RestoreDisk
import wce_triage.lib.util
from wce_triage.ops.ops_ui import ops_ui
from wce_triage.ops.partition_runner import make_usb_stick_partition_plan, make_efi_partition_plan

def _describe_task(task):
  return {"description": task.get_description(),
          "progress": task.progress,
          "time_estimate": task.time_estimate,
          "step" : task.task_number}


routes = aiohttp.web.RouteTableDef()

import socketio
wock = socketio.AsyncServer(async_mode='aiohttp', logger=True, cors_allowed_origins='*')

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
        print(resource)
        print(traceback.format_exc(exc))
        pass
      pass

    self.computer = None
    self.messages = ['WCE Triage Version 0.0.1']

    # wock (web socket) channels.
    self.channels = {}
    pass


  def note(self, message):
    self.messages.append(message)

    wock_ns = '/wock/message'
    print (self.channels.keys())
    if self.channels.get(wock_ns):
      wock.emit(message, wock_ns)
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
  async def triage(self):
    if self.computer is None:
      self.computer = Computer()
      self.overall_decision = self.computer.triage()
      self.note("Triage result is %s." % "good" if self.overall_decision else "bad")
      pass
    return self.computer


  @routes.get("/dispatch/triage.json")
  async def route_triage(request):
    """Handles requesting triage result"""
    
    global me
    if me.computer is None:
      await me.triage()
      pass
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
               "progress": 0,
               "elapseTime": 0,
               "mounted": "y" if disk.mounted else "n",
               "size": int(disk.get_byte_size() / 1073741824.0 + 0.5),
               "bus": "usb" if disk.is_usb else "ata",
               "model": disk.model_name }
              for disk in computer.disks ]

    jsonified = { "diskPages": 1, "disks": disks }
    return aiohttp.web.json_response(jsonified)


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


  @routes.post("/dispatch/load")
  async def route_load_image(request):
    """Load disk image to disk"""
    # FIXME: needs actual implementation
    global me
    devname = request.query.get("deviceName")
    imagefile = request.query.get("source")
    if imagefile:
      loop = asyncio.get_event_loop()
      with ThreadPoolExecutor() as execpool:
        await loop.run_in_executor(execpool, me.run_load_image, devname, imagefile)
        pass
      pass
    else:
      await me.note("No image file selected.")
      pass
    return aiohttp.web.json_response({ "pages": 1 })
  
  async def run_load_image(self, devname, imagefile):
    self.note("Disk image started")
    disk = Disk(device_name = devname)
    runner = RestoreDisk(wock_ui(wock, self.note), disk, imagefile,
                         pplan=make_usb_stick_partition_plan(disk), partition_id=1, partition_map='msdos',
                         newhostname="triage20")
    runner.prepare()
    await runner.preflight()
    await runner.explain()
    # FIXME: Don't run for now. See websock works.
    # runner.run()
    await self.note("Disk image finished")
    pass

  @routes.get("/dispatch/disk-load-status.json")
  async def route_disk_load_status(request):
    """Load disk image to disk"""
    # FIXME: needs actual implementation

    fake_status = { "pages": 1,
                    "steps": [ { "category": "Step-1", "progress": 100, "elapseTime": "100", "status": "done" },
                               { "category": "Step-2", "progress": 30, "elapseTime": "30", "status": "running" },
                               { "category": "Step-3", "progress": 0, "elapseTime": "0", "status": "waiting" },
                               { "category": "Step-4", "progress": 0, "elapseTime": "0", "status": "waiting" } ] }
    return aiohttp.web.json_response(fake_status)

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


  @routes.get("/dispatch/shutdown")
  async def route_shutdown(request):
    """shutdowns the computer."""
    global me
    shutdown_mode = request.query.get("mode", ["ignored"])
    if shutdown_mode == "poweroff":
      subprocess.run(['poweroff'])
    elif shutdown_mode == "reboot":
      subprocess.run(['reboot'])
    else:
      me.note("Shutdown command needs a query and ?mode=poweroff or ?mode=reboot is accepted.")
      raise HTTPNotFound()
      pass
    return aiohttp.web.json_response({})
  
  pass
  
@wock.event
def connect(wockid, environ):
  global me
  me.channels[wockid] = environ
  print("************** connect ************* " +  wockid)
  print(environ)
  pass


@wock.event
def disconnect(wockid):
  global me
  del me.channels[wockid]
  print('disconnect ' + wockid)
  pass

#
# WebScoket UI for Task Runner
#

class wock_ui(ops_ui):
  def __init__(self, wock, noter):
    self.wock = wock
    self.noter = noter
    self.last_report_time = datetime.datetime.now()
    pass


  # Called from preflight to just set up the flight plan
  async def report_tasks(self, total_time_estimate, tasks):
    print (tasks)
    await self.wock.emit("steps", { "load": { "total_estimate" : total_time_estimate,
                                              "steps" : [ _describe_task(task) for task in tasks ] } },
                         namespace="load")
    pass

  #
  async def report_task_progress(self, total_time, time_estimate, elapsed_time, progress, task):
    pass


  async def report_task_failure(self,
                                task_time_estimate,
                                elapsed_time,
                                progress,
                                task):
    pass

  async def report_task_success(self, task_time_estimate, elapsed_time, task):
    pass

  async def report_run_progress(self, 
                                step,
                                tasks,
                                total_time_estimate,
                                elapsed_time):
    pass

  # Used for explain. Probably needs better way
  async def describe_steps(self, steps):
    await self.wock.emit('steps', { "load": { "total_estimate": 0,
                                              "steps" : [ { "description": desc, "details": details } for desc, details in steps ] } },
                         namespace="load")
    pass

  # Log message. Probably better to be stored in file so we can see it
  # FIXME: probably should use python's logging.
  async def log(self, msg):
    self.noter(msg)
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
  logging.basicConfig(level=logging.DEBUG)

  fileout = logging.FileHandler("/tmp/httpserver.log")
  for logkind in ['aiohttp.access', 'aiohttp.client', 'aiohttp.internal', 'aiohttp.server', 'aiohttp.web', 'aiohttp.websocket', 'socketio.server']:
    thing = logging.getLogger(logkind)
    thing.setLevel(logging.DEBUG)
    thing.addHandler(fileout)
    pass
  
  # Create and configure the HTTP server instance
  the_root_url = u"{0}://{1}:{2}{3}".format("HTTP",
                                            arguments.host,
                                            arguments.port,
                                            "/index.html")
  loop = asyncio.get_event_loop()
  loop.set_debug(True)

  # Accept connection from everywhere
  app = aiohttp.web.Application(debug=True, loop=loop)
  wock.attach(app)
  cors = aiohttp_cors.setup(app)
  global me
  me = TriageWeb(app, arguments.rootdir, cors)

  print("Starting server, use <Ctrl-C> to stop...")
  print(u"Open {0} in a web browser.".format(the_root_url))
  aiohttp.web.run_app(app, host="0.0.0.0", port=arguments.port)
  pass
