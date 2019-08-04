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
from wce_triage.components.disk import Disk, Partition, DiskPortal, PartitionLister
from wce_triage.lib.util import *
from wce_triage.lib.timeutil import *
from wce_triage.ops.ops_ui import ops_ui
from wce_triage.lib.pipereader import *
from wce_triage.components import optical_drive as _optical_drive
from wce_triage.components import sound as _sound
from wce_triage.lib.disk_images import *
import wce_triage.version


tlog = get_triage_logger()
routes = aiohttp.web.RouteTableDef()
import socketio
wock = socketio.AsyncServer(async_mode='aiohttp', logger=get_triage_logger(), cors_allowed_origins='*')


@routes.get('/version.json')
async def route_version(request):
  """Get the version number of backend"""
  # FIXME: Front end version is in manifest.
  fversion = "1.0.0"
  try:
    with open('/usr/local/share/wce/wce-triage-ui/manifest.json') as frontend_manifest:
      manifest = json.load(frontend_manifest)
      fversion = manifest.get('version', "1.0.0")
      pass
    pass
  except Exception as exc:
    tlog.info('Reading /usr/local/share/wce/wce-triage-ui/manifest.json failed with exception. ' + traceback.format_exc())
    pass

  jsonified = { "version": {"backend": wce_triage.version.TRIAGE_VERSION, "frontend": fversion }}
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
# This is ugly as hell. json_ui needs a better design.
#
def update_runner_status(runner_status, progress):
  # load image event has two types, one from report_task_progress and other from report_tasks
  # report_tasks contains the tasks, and task progress only updates the small part.

  # If it includes all of tasks, use it.
  if progress.get("tasks"):
    runner_status = {"tasks": progress["tasks"]}
    pass

  # If it includes the task and it's step number,
  # update the task.
  # FIXME: Probalby it's better to replace the task
  if progress.get("task") and progress.get("step"):
    step = progress["step"]
    task = progress["task"]
    tasks = runner_status.get("tasks")
    if tasks and step < len(tasks):
      runner_status["tasks"][step]["taskProgress"] = task["taskProgress"]
      runner_status["tasks"][step]["taskElapse"] = task["taskElapse"]
      if task["taskMessage"]:
        runner_status["tasks"][step]["taskMessage"] = task["taskMessage"]
        pass
      runner_status["tasks"][step]["taskStatus"] = task["taskStatus"]
      pass
    pass
  return runner_status

#
# WebSocket sender.
#
# is a FIFO queue. You put in a message you want to send using _send().
# http server polls the out side of queue, and send out a packet to
# the listener.
#
# What's in the queue?
# The element is 3-item length tuple.
# 1: the sequence number of element.
# 2: WebSocket's event
# 3: WebSocket's data
#
# The event name here and UI side websocket need to match or else the
# message is ignored.
# FIXME: Have some kind of dictionary between the front/back ends.
#
# Known event type: message, diskupdate, triageupdate, loadimage, saveimage
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
      await asyncio.sleep(0.1)
      pass
    pass

  async def flush():
    global me
    running = True
    while running:
      try:
        elem = Emitter.queue.get(block=False)
        tlog.debug("EMITTER: sending %d: '%s' '%s'" % (elem[0], elem[1], elem[2]))
        message = elem[2]
        message['_sequence_'] = elem[0]
        await wock.emit(elem[1], message)
        me.peek_message(elem[1], message)
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
    Emitter._send('message', {"message": message,
                              "severity": 1})
    pass

  # This is to send alert message (aka popping up a dialog
  def alert(message):
    tlog.info(message)
    Emitter._send('message', {"message": message,
                              "severity": 2})
    pass
  pass

#
# id: ID used for front/back communication
# name: displayed on web
# arg: arg used for restore image runner.
#
WIPE_TYPES = [ {"id": "nowipe", "name": "No Wipe", "arg": ""},
               {"id": "wipe", "name": "Full wipe", "arg": "-w" },
               {"id": "shortwipe", "name": "Wipe first 1Mb", "arg": "--quickwipe" } ];

#
# TriageWeb
#
# NOTE: Unfortunately, aiohttp dispatch doesn't give me "self", so only alternative
# is to use a singleton. IOW, this class is nothing more than a namespace.
#
class TriageWeb(object):
  
  wiper_output_re = re.compile(r'^WIPE: python3\.stderr:(.*)')

  def __init__(self, app, root_url, rootdir, wcedir, cors, loop, live_triage):
    """
    HTTP request handler for triage
    """

    self.root_url = root_url
    self.live_triage = live_triage
    self.wcedir = wcedir
    self.asset_path = os.path.join(wcedir, "triage", "assets")

    app.router.add_routes(routes)

    app.router.add_static("/wce-disk-images", os.path.join(wcedir, "wce-disk-images"))
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

    self.loading_status = { "pages": 1, "tasks": [], "diskRestroing": False }
    self.saving_status = { "pages": 1, "tasks": [], "diskSaving": False}
    self.wiping_status = { "pages": 1, "tasks": [], "diskWiping": False }

    # wock (web socket) channels.
    self.channels = {}

    self.target_disks = []

    # FIXME: ? It might make sense to refactor these processes for reducing code.
    self.restore = None
    self.saver = None
    self.wiper = None
    self.optests = []

    self.wock = wock

    self.disk_portal = DiskPortal()

    asyncio.ensure_future(TriageWeb._periodic_update(), loop=loop)
    pass

  #
  async def _periodic_update():
    global me
    while True:
      await asyncio.sleep(2)
      if me.triage_timestamp is None:
        continue

      computer = me.computer
      (added, changed, removed) = me.disk_portal.detect_disks()
      
      if added or changed or removed:
        disks = {"disks": [ jsoned_disk(disk) for disk in me.disk_portal.disks ]}
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
    #
    pass

  def peek_message(self, event, message):
    '''get to observe the message sent to the browser. This gives the
    HTTP server to see what's sent to the UI and have chance to update
    the status so when UI comes back and asks staus, the server can reply.'''
    # so when browser asks with "get", I can answer the same result.
    # This is called from emitter as it sends the status to the browser.
    if event == "loadimage":
      self.loading_status = update_runner_status(self.loading_status, message)
      pass
    elif event == "saveimage":
      self.saving_status = update_runner_status(self.saving_status, message)
      pass
    elif event == "zerowipe":
      self.wiping_status = update_runner_status(self.wiping_status, message)
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
    hello = me.computer is None
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
    for asset in os.listdir(me.asset_path):
      if asset.endswith(".mp3"):
        music_file = os.path.join(me.asset_path, asset)
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

      
      PipeReader.add_to_event_loop(optical_test.stdout, me.watch_optest, "stdout")
      PipeReader.add_to_event_loop(optical_test.stdout, me.watch_optest, "stderr")
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
        if process.returncode is not None:
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


  def watch_optest(self, pipereader):
    line = pipereader.readline()
    if line == b'':
      tlog.debug("FromOptest: optical test stream ended.")
      pipereader.remove_reader()
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
    global me

    # Loading doesn't have to come from http server, but this is a good test for now.
    disk_images = os.path.join(me.wcedir, "wce-disk-images", "wce-disk-images.json")
    if os.path.exists(disk_images):
      resp = aiohttp.web.FileResponse(disk_images)
      resp.content_type="application/json"
      return resp
    return aiohttp.web.json_response({ "sources": get_disk_images(root_url=me.root_url) })


  @routes.get("/remote-disk-images.json")
  async def route_disk_images(request):
    """Returning the disk image for remote loading.
       This is probably not going to be used for serving installation payload.
       It should be done by the http server like lighttpd
    """
    global me
    return aiohttp.web.json_response({ "sources": get_disk_images(root_url=me.root_url) })


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


  # Disk wipe types.
  #  
  @routes.get("/dispatch/wipe-types.json")
  async def route_restore_types(request):
    """Returning wipe types."""
    return aiohttp.web.json_response({ "wipeTypes": WIPE_TYPES})


  @routes.post("/dispatch/load")
  async def route_load_image(request):
    """Load disk image to disk"""
    global me

    me.target_disks = get_target_devices_from_request(request)
    if me.target_disks is None:
      raise HTTPServiceUnavailable()

    # Resetting the state - hack...
    if request.query.get('source'):
      me.load_disk_options = request.query
      me.start_load_disks('start from request')
    else:
      Emitter.note("No image file selected.")
      await Emitter.flush()
      pass
    return aiohttp.web.json_response({})

  def _get_load_option(self, tag):
    value = self.load_disk_options.get(tag)
    if isinstance(value, tuple):
      value = value[0]
      pass
    return value

  def start_load_disks(self, log):
    if not self.target_disks:
      return

    devname = self.target_disks[0]
    self.target_disks = self.target_disks[1:]
    tlog.debug(log + " Targets : " + ",".join(self.target_disks))

    # restore image runs its own course, and output will be monitored by a call back
    # restore_image_runner.py [-h] [-m HOSTNAME] [-p] [-c] [-w] [--quickwipe] devname imagesource imagesize restore_type
    argv = ['python3', '-m', 'wce_triage.ops.restore_image_runner']

    wipe_request = self._get_load_option("wipe")
    for wipe_type in WIPE_TYPES:
      if wipe_type.get("id") == wipe_request:
        if wipe_type.get("arg"):
          argv.append(wipe_type["arg"])
          pass
        break
      pass

    newhostname = self._get_load_option("newhostname")
    if newhostname:
      argv.append('-m')
      argv.append(newhostname)
      pass

    imagefile = self._get_load_option("source")
    imagefile_size = self._get_load_option("size") # This comes back in bytes from sending sources with size. value in query is always string.
    restore_type = self._get_load_option("restoretype")

    argv = argv + [devname, imagefile, imagefile_size, restore_type]
    tlog.debug(argv)

    # FIXME: I think I can refactor the run subprocess / gather thing. Up to this point,
    # this is about making argv, after this, thing to do is the same. However, looking at the
    # callbacks, there aren't much to do in it so how much I can buy from refactoring is not much.

    self.restore = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    PipeReader.add_to_event_loop(self.restore.stdout, me.restore_progress_report, "loadimage")
    PipeReader.add_to_event_loop(self.restore.stderr, me.restore_progress_report, "message")
    return

  # 
  def _runner_progress_report(self, runner, pipereader):
    line = pipereader.readline()
    if line == b'':
      if pipereader.asyncio_reader:
        try:
          pipereader.remove_from_event_loop()
          pass
        except Exception as exc:
          tlog.debug("%s: remove_reader %s" % (runner, traceback.format_exc()))
          pass
        pass
      pass
    elif line is not None:
      if line.strip() != '':
        tlog.debug("%s: '%s'" % (runner, line))
        if pipereader.tag == runner:
          # This is a message from loader
          try:
            packet = json.loads(line)
            Emitter._send(packet['event'], packet['message'])
          except Exception as exc:
            tlog.info("%s: BAD LINE '%s'\n%s" % (runner, line, traceback.format_exc()))
            Emitter.note(line)
            pass
          pass
        else:
          Emitter.note(line)
          pass
        pass
      pass
    pass
  

  # Callback for checking the restore process
  def _runner_check_process(self, runner, process, log):
    if process:
      # tlog.debug(log + " Restore is running")
      process.poll()
      if process.returncode is not None:
        returncode = process.returncode
        if returncode is not 0:
          Emitter.note("Restore failed with error code %d" % returncode)
          pass
        # hack to reset the runner state - no runner id.
        Emitter._send(runner, {"device": ''})
        pass
      pass
    pass

  def restore_progress_report(self, pipereader):
    '''Callback for checking the output of restore process'''
    self._runner_progress_report("loadimage", pipereader)
    if self.restore:
      self._runner_check_process("loadimage", self.restore, 'check restore process from status')
      if self.restore.returncode is not None:
        self.restore = None
        self.start_load_disks("loadimage finished.")
      pass
    pass

  @routes.post("/dispatch/stop-load")
  async def route_stop_load_image(request):
    global me
    if me.restore and me.restore.returncode is None:
      me.restore.terminate()
      pass
    return aiohttp.web.json_response({})


  @routes.get("/dispatch/disk-load-status.json")
  async def route_disk_load_status(request):
    """Progress of load disk image to disk"""
    global me
    running = me.restore and me.restore.returncode is None
    loading_status = me.loading_status
    loading_status['diskRestoring'] = running
    return aiohttp.web.json_response(loading_status)


  @routes.get("/dispatch/disk-save-status.json")
  async def route_disk_save_status(request):
    """Progress of save disk image"""
    global me
    running = me.saver and me.saver.returncode is None
    saving_status = me.loading_status
    saving_status['diskSaving'] = running
    return aiohttp.web.json_response(me.saving_status)


  @routes.get("/dispatch/wiping-status.json")
  async def route_wiping_status(request):
    """Progress of disk wiping."""
    global me
    return aiohttp.web.json_response(me.wiping_status)

  @routes.get("/dispatch/download")
  async def route_download_image(request):
    """Download disk image. not implemented yet."""
    return aiohttp.web.json_response({})


  @routes.post("/dispatch/save")
  async def route_save_image(request):
    """Create disk image and save"""
    global me
    devname = request.query.get("deviceName")
    saveType = request.query.get("type")
    destdir = request.query.get("destination")

    if saveType is None:
      tlog.info("saveimage - image type is not given.")
      raise HTTPServiceUnavailable()

    await me.wock.emit("saveimage", { "device": devname, "runStatus": "", "totalEstimate" : 0, "tasks" : [] })

    target = None
    for disk in me.disk_portal.disks:
      if disk.device_name == devname:
        target = disk
        break
      pass

    if target is None:
      tlog.info("No such disk " + devname)
      raise HTTPServiceUnavailable()
      
    disk = me.disk_portal.find_disk_by_device_name(devname)
    lister = PartitionLister(disk)
    lister.execute()
    part = disk.find_partition_by_file_system('ext4')
    if part is None:
      for partition in disk.partitions:
        tlog.debug(str(partition))
        pass
      Emitter.alert("Device %s has no EXT4 partition for imaging." % disk.device_name)
      return
    
    partition_id = disk.get_partition_id(part)
    if partition_id is None:
      Emitter.alert("Partition %s has not valid ID." % part.device_name)
      return
    
    # saveType is a single word coming back from read_disk_image_types()
    image_type = None
    for _type in read_disk_image_types():
      if _type["id"] == saveType :
        image_type = _type
        break
      pass
    if image_type is None:
      Emitter.alert("Image type %s is not known." % saveType)
      return
    
    destdir = image_type.get('catalogDirectory')
    if destdir is None:
      Emitter.alert("Imaging type info %s does not include the catalog directory." % image_type.get("id"))
      return
    
    # save image runs its own course, and output will be monitored by a call back
    me.saver = subprocess.Popen( ['python3', '-m', 'wce_triage.ops.create_image_runner', devname, str(partition_id), destdir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    PipeReader.add_to_event_loop(me.saver.stdout, me.saver_progress_report, "saveimage")
    PipeReader.add_to_event_loop(me.saver.stderr, me.saver_progress_report, "message")
    return aiohttp.web.json_response({})

  def saver_progress_report(self, pipereader):
    self._runner_progress_report("saveimage", pipereader)
    if self.saver:
      self._runner_check_process("saveimage", self.saver, ' check saver process from progress report')
      if self.saver.returncode is not None:
        self.saver = None
        pass
      pass
    pass

  @routes.post("/dispatch/wipe")
  async def route_wipe(request):
    global me

    me.disk_portal.detect_disks()
    disks = me.disk_portal.disks

    me.target_disks = get_target_devices_from_request(request)
    if me.target_disks is None:
      raise HTTPServiceUnavailable()

    target = None
    for disk in disks:
      if disk.device_name in me.target_disks:
        if disk.mounted:
          return aiohttp.web.json_response({})
          pass
        target = disk
        break
      pass
        
    me.start_wiper()
    return aiohttp.web.json_response({})


  def start_wiper(self):
    if not self.target_disks:
      return

    devname = self.target_disks[0]
    self.target_disks = self.target_disks[1:]
    tlog.debug( "Wipe targets : " + ",".join(self.target_disks))

    # wiper image runs its own course, and output will be monitored by a call back
    me.wiper = subprocess.Popen( ['python3', '-m', 'wce_triage.bin.wipedriver', devname], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    PipeReader.add_to_event_loop(me.wiper.stdout, me.wiper_progress_report, "message")
    PipeReader.add_to_event_loop(me.wiper.stderr, me.wiper_progress_report, "wipe")
    pass


  def wiper_progress_report(self, pipereader):
    line = pipereader.readline()
    if line == b'':
      asyncio.get_event_loop().remove_reader(pipereader.pipe)
      pass
    elif line is not None:
      if line.strip() != "":
        tlog.debug("FromWiper: '%s'" % line)
        if pipereader.tag == "wipe":
          # This is a progress report from wiper driver. Unlike json_ui, the output contains the
          # prefix from processDriver.
          matched = self.wiper_output_re.match(line)
          if matched:
            packet = json.loads(matched.group(1))
            Emitter._send(packet['event'], packet['message'])
            pass
          else:
            tlog.debug("Unrecognized line from wiper: " +line)
            Emitter.note(line)
            pass
          pass
        else:
          # This is from stdout
          tlog.debug(line)
          Emitter.note(line)
          pass
        pass
      pass

    if self.wiper:
      self._runner_check_process("wipe", self.wiper, " check process from wipe update")
      if self.wiper.returncode is not None:
        self.wiper = None
        self.start_wiper()
        pass
      pass
    pass


  @routes.post("/dispatch/stop-wipe")
  async def route_stop_wipe(request):
    global me
    if me.wiper and me.wiper.returncode is None:
      me.wiper.terminate()
      pass
    return aiohttp.web.json_response({})

  # FIXME:
  @routes.get("/dispatch/disk-wipe-status.json")
  async def route_disk_wipe_status(request):
    global me
    wiper_running = me.wiper and me.wiper.returncode is None
    wiping_status = me.wiping_status
    wiping_status["diskWiping"] = wiper_running
    return aiohttp.web.json_response(wiping_status)

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
    global me
    unmountingDisks = get_target_devices_from_request(request)
    tlog.debug("unmounting " + ",".join(unmountingDisks))
    response = []

    for disk in me.disk_portal.disks:
      if disk.device_name in unmountingDisks:
        mounted = disk.mounted
        if mounted:
          # Normally, partitions are not detected.
          lister = PartitionLister(disk)
          lister.execute()
          mounted = False
          for partition in disk.partitions:
            tlog.debug("Unmounting partition %s" % partition.device_name)
            umount = subprocess.run(["umount", partition.device_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if umount.returncode != 0:
              mounted = True
              tlog.debug("Unmounting partition %s failed with retcode %d" % (partition.device_name, umount.returncode))
              pass
            out = umount.stdout.decode('iso-8859-1').strip()
            err = umount.stderr.decode('iso-8859-1').strip()
            if out:
              tlog.debug(out)
              pass
            if err:
              tlog.debug(err)
              pass
              
            pass
          disk.mounted = mounted
          pass
        else:
          tlog.debug("disk %s is not mounted." % disk.device_name)
          pass
        pass
      else:
        tlog.debug('ummounting %s is not requested.' % disk.device_name)
        pass
      response.append({ "device": disk.device_name, "mounted": disk.mounted })
      pass
    return aiohttp.web.json_response(response)

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


def get_target_devices_from_request(request):
  devname = request.query.get("deviceName")
  devnames = request.query.get("deviceNames")

  if devnames is not None:
    target_disks = devnames.split(',')
    pass
  elif devname and devnames is None:
    target_disks = [devname]
  else:
    target_disks = None
    pass
  return target_disks



# Define and parse the command line arguments
import socket
cli = ArgumentParser(description='Example Python Application')
cli.add_argument("-p", "--port", type=int, metavar="PORT", dest="port", default=8312)
cli.add_argument("--host", type=str, metavar="HOST", dest="host", default=socket.getfqdn())
cli.add_argument("--rootdir", type=str, metavar="WCE_TRIAGE_UI_ROOTDIR", dest="rootdir", default=None)
cli.add_argument("--wcedir", type=str, metavar="WCE_ROOT_DIR", dest="wcedir", default="/usr/local/share/wce")
cli.add_argument("--live-triage", dest="live_triage", action='store_true')
arguments = cli.parse_args()

# If the module is invoked directly, initialize the application
if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO,
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                      filename='/tmp/triage.log')
  tlog = get_triage_logger()
  tlog.setLevel(logging.DEBUG)
  
  # Create and configure the HTTP server instance
  the_root_url = u"{0}://{1}:{2}".format("HTTP",
                                         arguments.host,
                                         arguments.port)
  loop = asyncio.get_event_loop()
  # loop.set_debug(True)

  # Accept connection from everywhere
  tlog.info("Starting app.")
  app = aiohttp.web.Application(debug=True, loop=loop)
  cors = aiohttp_cors.setup(app)
  wock.attach(app)
  global me
  wcedir = arguments.wcedir
  rootdir = arguments.rootdir
  if rootdir is None:
    rootdir = os.path.join(wcedir, "wce-triage-ui")
    pass
  me = TriageWeb(app, the_root_url, rootdir, wcedir, cors, loop, arguments.live_triage)

  tlog.info("Starting server, use <Ctrl-C> to stop...")
  tlog.info(u"Open {0}{1} in a web browser.".format(the_root_url, "/index.html"))
  Emitter.register(loop)

  aiohttp.web.run_app(app, host="0.0.0.0", port=arguments.port, access_log=get_triage_logger())
  pass
