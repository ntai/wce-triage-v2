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
import os
import sys
import re
import subprocess
from urllib.parse import parse_qs
import logging, logging.handlers
import asyncio

from wce_triage.components.computer import Computer
from wce_triage.ops.restore_image_runner import RestoreDisk
from wce_triage.ops.create_image_runner import ImageDisk
from wce_triage.components.disk import Disk, Partition
import wce_triage.lib.util

import pathlib
routes = aiohttp.web.RouteTableDef()

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


@routes.get('/bang')
async def route_version(request):
  raise Exception("Want to see something here.")
  return aiohttp.web.json_response({})


class TriageWeb(object):
  me = None
  asset_path = "/usr/local/share/wce/triage/assets"

  def __init__(self, app, rootdir, cors):
    """
    HTTP request handler for triage
    """
    self.me = self
    app.router.add_routes(routes)
    app.router.add_static("/", rootdir)

    for resource in app.router._resources:
      cors.add(resource, { '*': aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*") })
      pass
    pass
  

  @routes.get("/")
  async def route_triage(request):
    raise aiohttp.web.HTTPFound('/index.html')
    return None


  @routes.get("/dispatch/triage.json")
  async def route_triage(request):
    """Handles requesting triage result"""
    
    computer = Computer()
    overall_decision = computer.triage()

    # decision comes back as tuple, make it to the props for jsonify
    jsonified = { "components": [ {"component": thing, "result": "Good" if good else "Bad", "details": dtl} for thing, good, dtl in computer.decisions ] }
    print( "triage " + str(jsonified))
    return aiohttp.web.json_response(jsonified)


  @routes.get("/dispatch/disks.json")
  async def route_disks(request):
    """Handles getting the list of disks"""

    computer = Computer()
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

    jsonified = { "network": netstat }
    return aiohttp.web.json_response(jsonified)


  @routes.get("/dispatch/disk-images.json")
  async def route_disk_images(request):
    """Handles getting the list of disk images"""
    images = { "sources": wce_triage.lib.util.get_disk_images() }
    return aiohttp.web.json_response(images)


  @routes.get("/dispatch/load")
  async def route_load_image(request):
    """Load disk image to disk"""

    fake_status = { "pages": 1,
                    "sources": [ "wce-1.tar.gz", "wce-2.tar.gz", "wce-3.tar.gz" ] }

    return aiohttp.web.json_response(fake_status)


  @routes.get("/dispatch/disk-load-status.json")
  async def route_disk_load_status(request):
    """Load disk image to disk"""

    fake_status = { "pages": 1,
                    "steps": [ { "category": "Step-1", "progress": 100, "elapseTime": "100", "status": "done" },
                               { "category": "Step-2", "progress": 30, "elapseTime": "30", "status": "running" },
                               { "category": "Step-3", "progress": 0, "elapseTime": "0", "status": "waiting" },
                               { "category": "Step-4", "progress": 0, "elapseTime": "0", "status": "waiting" } ] }

    return aiohttp.web.json_response(fake_status)

  @routes.get("/dispatch/save")
  async def route_save_image(request):
    """Load disk image to disk"""
    # Not implemented yet
    return aiohttp.web.json_response({})


  @routes.get("/dispatch/shutdown")
  async def route_shutdown(request):
    """shutdowns the computer."""
    shutdown_mode = query_get(request.query, "mode", default="ignore")
    if shutdown_mode == "poweroff":
      subprocess.run(['poweroff'])
    elif shutdown_mode == "reboot":
      subprocess.run(['reboot'])
    else:
      raise HTTPNotFound()
      pass
    return aiohttp.web.json_response({})
  
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
  for logkind in ['aiohttp.access', 'aiohttp.client', 'aiohttp.internal', 'aiohttp.server', 'aiohttp.web', 'aiohttp.websocket']:
    thing = logging.getLogger(logkind)
    thing.setLevel(logging.DEBUG)
    thing.addHandler(fileout)
    pass
  
  # Create and configure the HTTP server instance
  global the_root_url
  the_root_url = u"{0}://{1}:{2}{3}".format("HTTP",
                                            arguments.host,
                                            arguments.port,
                                            "/index.html")
  loop = asyncio.get_event_loop()
  loop.set_debug(True)

  # Accept connection from everywhere
  app = aiohttp.web.Application(debug=True, loop=loop)
  cors = aiohttp_cors.setup(app)
  TriageWeb(app, arguments.rootdir, cors)

  print("Starting server, use <Ctrl-C> to stop...")
  print(u"Open {0} in a web browser.".format(the_root_url))
  aiohttp.web.run_app(app, host="0.0.0.0", port=arguments.port)
  pass
