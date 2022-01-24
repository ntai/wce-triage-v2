""" 
The MIT License (MIT)
Copyright (c) 2021 - Naoyuki Tai

WCE Triage HTTP server - 
and webscoket server
"""

from flask import Flask

from flask_socketio import SocketIO, send, emit

from ..version import TRIAGE_VERSION, TRIAGE_TIMESTAMP
from ..const import const

from argparse import ArgumentParser
import json
import os, re, subprocess, datetime, asyncio, traceback, queue
import logging, logging.handlers

from ..components.computer import Computer
from ..components.disk import DiskPortal, PartitionLister
from ..lib.util import get_triage_logger, init_triage_logger
# from ..lib.timeutil import in_seconds
from ..lib.pipereader import PipeReader
# from ..components import optical_drive as _optical_drive
from ..components import sound as _sound
from ..lib.disk_images import get_disk_images, read_disk_image_types
from ..components import network as _network
# from ..lib.cpu_info import cpu_info



tlog = get_triage_logger()

@app.routes('/version.json')
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

  jsonified = { "version": {"backend": TRIAGE_VERSION + "-" + TRIAGE_TIMESTAMP, "frontend": fversion }}
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
          "size": round(disk.get_byte_size() / 1000000), # in MB (not MiB)
          "bus": "usb" if disk.is_usb else "ata",
          "model": disk.model_name,
          "vendor": disk.vendor,
          "serial_no": disk.serial_no,
          "smart": disk.smart,
          "smart_enabled": disk.smart_enabled,
  }

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

  def __init__(self, app, wce_share_url, rootdir, wcedir, cors, loop, live_triage, load_disk_options):
    """
    HTTP request handler for triage
    """

    self.wce_share_url = wce_share_url
    self.live_triage = live_triage
    self.wcedir = wcedir
    self.asset_path = os.path.join(wcedir, "triage", "assets")
    self.load_disk_options = load_disk_options
    self.autoload = True if self.load_disk_options else False
    self.sync_disk_image_options = {}
    
    app.router.add_routes(routes)

    app.router.add_static("/wce", os.path.join(wcedir))
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
    self.syncing_status = { "tasks": [] }

    # wock (web socket) channels.
    self.channels = {}
    self.target_disks = []
    self.sync_target_disks = []

    # FIXME: ? It might make sense to refactor these processes for reducing code.
    # It also helps to do parallel exec.
    self.restore = None
    self.saver = None
    self.wiper = None
    self.optests = []
    self.cpu_info = None # This is the process instance of cpu info
    self.benchmark = None # THis is the output of cpu info aka benchmark
    self.syncer = None
    
    self.wock = wock

    self.disk_portal = DiskPortal()

    asyncio.ensure_future(TriageWeb._periodic_update(), loop=loop)
    pass

  #
  # This should be in its own thread
  # 
  def _periodic_update():
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
    elif event == "diskimage":
      self.syncing_status = update_runner_status(self.syncing_status, message)
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
    await me.triage()
    computer = me.computer

    decisions = [ { "component": "Overall", "result": me.overall_decision } ] + computer.decisions
    jsonified = { "components":  decisions }
    return aiohttp.web.json_response(jsonified)


  # get_cpu_info is potentially ver slow for older computers as this runs a
  # cpu benchmark.
  async def get_cpu_info(self):
    if self.cpu_info is None:
      tlog.debug("get_cpu_info: starting")
      self.cpu_info = subprocess.Popen("python3 -m wce_triage.lib.cpu_info", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      PipeReader.add_to_event_loop(self.cpu_info.stdout, self.watch_cpu_info, "stdout")
      tlog.debug("get_cpu_info: started")
      pass

    while self.benchmark is None:
      tlog.debug("get_cpu_info: waiting")
      await asyncio.sleep(1)
      pass
    return self.benchmark

  @routes.get("/dispatch/cpu_info.json")
  async def route_cpu_info(request):
    """Handles getting CPU rating """
    global me
    benchmark = await me.get_cpu_info()
    jsonified = { "cpu_info": benchmark }
    return aiohttp.web.json_response(jsonified)


  def watch_cpu_info(self, pipereader):
    line = pipereader.readline()
    if line == b'':
      tlog.debug("watch_cpu_info: done")
      pipereader.remove_from_event_loop()
      pass
    elif line is not None:
      if len(line.strip()) == 0:
        return
      try:
        tlog.debug("watch_cpu_info: '%s'" % line)
        self.benchmark = json.loads(line)
      except Exception as exc:
        tlog.info("watch_cpu_info - json.loads: '%s'\n%s" % (line, traceback.format_exc()))
        pass
      pass
    pass

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
    device_name = request.query.get('deviceName')
    if device_name is None:
      raise HTTPServiceUnavailable()
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
        # FIXME: Do something meaningful, like send a wock message.
        if updated:
          tlog.info("updated")
          pass
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
    
    reply = [ jsoned_optical(optical) for optical in me.computer.opticals._drives ]
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
      pipereader.remove_from_event_loop()
      pass
    elif line is not None:
      if len(line.strip()) == 0:
        return
        
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
        tlog.info("FromOptest: '%s'\n%s" % (line, exc.format_exc()))
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
    for netdev in _network.detect_net_devices():
      netstat.append( { "device": netdev.device_name, "carrier": netdev.is_network_connected() } )
      computer.update_decision( {"component": "Network",
                                 "device": netdev.device_name},
                                {"result": netdev.is_network_connected(),
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
    return aiohttp.web.json_response({ "sources": get_disk_images(wce_share_url=me.wce_share_url) })

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
  async def route_wipe_types(request):
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
          tlog.debug("%s: remove_from_event_loop %s" % (runner, traceback.format_exc()))
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
    partid = request.query.get("partition", default="Linux")

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

    part = disk.find_partition(partid)
    if part is None:
      part = disk.find_partition_by_file_system('ext4')
      pass
    
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
    args = ['python3', '-m', 'wce_triage.ops.create_image_runner', devname, str(partition_id), destdir]
    tlog.info("saveimage - " + " ".join(args))
    me.saver = subprocess.Popen( args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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

    for disk in disks:
      if disk.device_name in me.target_disks:
        if disk.mounted:
          return aiohttp.web.json_response({})
          pass
        break
      pass
        
    me.start_wiper()
    return aiohttp.web.json_response({})


  def start_wiper(self):
    if not self.target_disks:
      return

    cmd = ['python3', '-m', 'wce_triage.bin.multiwipe'] + self.target_disks
    self.target_disks = []

    me.wiper = subprocess.Popen( cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    PipeReader.add_to_event_loop(me.wiper.stdout, me.wiper_progress_report, "message")
    PipeReader.add_to_event_loop(me.wiper.stderr, me.wiper_progress_report, "wipe")
    pass


  def wiper_progress_report(self, pipereader):
    line = pipereader.readline()
    if line == b'':
      pipereader.remove_from_event_loop()
      pass
    elif line is not None:
      if line.strip() != "":
        tlog.debug("FromWiper: '%s'" % line)
        if pipereader.tag == "wipe":
          # This is a progress report from wiper driver. Unlike json_ui, the output contains the
          # prefix from processDriver.
          try:
            packet = json.loads(line)
            Emitter._send(packet['event'], packet['message'])
            pass
          except:
            tlog.info("Unrecognized line from wiper: " +line)
            pass
          pass
        else:
          # This is from stdout
          tlog.info(line)
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

  # FIXME: Not implemented yet
  @routes.post("/dispatch/mount")
  async def route_mount_disk(request):
    """Mount disk"""
    global me
    me.disk_portal.detect_disks()
    disks = me.disk_portal.disks

    requested = request.query.get("deviceName")
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
          Emitter.note(traceback.format_exc())
          await Emitter.flush()
          pass
        pass
      pass
    return aiohttp.web.json_response({})

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

# ============================================================================
# sync and clean
#
  @routes.post("/dispatch/sync")
  async def route_sync_disk_images(request):
    """sync disk images from the source to selected disks"""
    global me

    me.sync_target_disks = get_target_devices_from_request(request)
    if me.sync_target_disks is None:
      raise HTTPServiceUnavailable()

    if request.query.get('sources'):
      me.sync_disk_image_options = request.query
      me.start_sync_disk_images('start sync from request')
    else:
      Emitter.note("No image file selected.")
      await Emitter.flush()
      pass
    return aiohttp.web.json_response({})

  @routes.post("/dispatch/clean")
  async def route_sync_disk_images(request):
    """clean disk images from the target disks"""
    global me

    me.sync_target_disks = get_target_devices_from_request(request)
    if me.sync_target_disks is None:
      raise HTTPServiceUnavailable()

    me.sync_disk_image_options = {}
    me.start_sync_disk_images('start sync from request', clean=True)
    return aiohttp.web.json_response({})


  def _get_sync_disk_image_option(self, tag):
    value = self.sync_disk_image_options.get(tag)
    if isinstance(value, tuple):
      value = value[0]
      pass
    return value

  def start_sync_disk_images(self, log, clean=False):
    if not self.sync_target_disks:
      return

    if clean:
      # clean
      argv = ['python3', '-m', 'wce_triage.ops.sync_image_runner', ",".join(self.sync_target_disks)] + ["clean"]
      pass
    else:
      imagefiles = self._get_sync_disk_image_option("sources")

      if len(imagefiles) == 0 or self.sync_target_disks == 0:
        tlog.debug("SYNC: imagefile is none, or sync target disk is none. Check the sync_disk_image_options")
        tlog.debug(self.sync_disk_image_options)
        argv = ['true']
      else:
        argv = ['python3', '-m', 'wce_triage.ops.sync_image_runner', ",".join(self.sync_target_disks)] + imagefiles.split(',')
        pass
      pass
    tlog.debug("SYNC: " + " ".join(argv))

    # FIXME: I think I can refactor the run subprocess / gather thing. Up to this point,
    # this is about making argv, after this, thing to do is the same. However, looking at the
    # callbacks, there aren't much to do in it so how much I can buy from refactoring is not much.

    self.syncer = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    PipeReader.add_to_event_loop(self.syncer.stdout, me.diskimage_progress_report, "diskimage")
    PipeReader.add_to_event_loop(self.syncer.stderr, me.diskimage_progress_report, "message")
    return

  def diskimage_progress_report(self, pipereader):
    '''Callback for checking the output of diskimage ops process'''
    self._runner_progress_report("diskimage", pipereader)
    if self.syncer:
      self._runner_check_process("diskimage", self.syncer, 'check disk image operation process from status')
      if self.syncer.returncode is not None:
        self.syncer = None
        self.sync_target_disks = []
        pass
      pass
    pass

  @routes.get("/dispatch/sync-status.json")
  async def route_sync_status(request):
    """Progress of sync image to disk"""
    global me
    running = me.syncer and me.syncer.returncode is None
    syncing_status = me.syncing_status
    syncing_status['syncing'] = running
    return aiohttp.web.json_response(syncing_status)

# ============================================================================

  @routes.post("/dispatch/rename")
  async def route_rename_image(request):
    """Rename a disk image file.
Error status report is a lot to be desired.
"""
    global me

    name_from = request.query.get("from")
    name_to = request.query.get("to")
    restoretype = request.query.get("restoretype")

    for disk_image in get_disk_images():
      if disk_image['name'] != name_from or disk_image['restoreType'] != restoretype:
        continue
      
      fullpath = disk_image['fullpath']
      parent_dir = os.path.split(fullpath)[0]
      to_path = os.path.join(parent_dir, name_to)
      try:
        os.rename(fullpath, to_path)
      except Exception as exc:
        # FIXME: better response?
        tlog.info("RENAME failed - %s/%s.\n%s" % (restoretype, name_from, traceback.format_exc()))
        raise HTTPServiceUnavailable()
        pass
      disk_image['name'] = name_to
      disk_image['fullpath'] = to_path
      return aiohttp.web.json_response(disk_image)

    # FIXME: better response?
    tlog.info("RENAME failed - %s/%s not found." % (restoretype, name_from))
    raise HTTPNotFound()
    pass

  @routes.post("/dispatch/delete")
  async def route_rename_image(request):
    """clean: Delete a disk image file.
Error status report is a lot to be desired.
"""
    global me

    name = request.query.get("name")
    restoretype = request.query.get("restoretype")

    for disk_image in get_disk_images():
      if disk_image['name'] != name or disk_image['restoreType'] != restoretype:
        continue
      
      fullpath = disk_image['fullpath']
      try:
        tlog.debug( "Delete '%s'" % fullpath)
        os.remove(fullpath)
        tlog.debug( "Delete '%s' succeeded." % fullpath)
        return aiohttp.web.json_response({})
      except Exception as exc:
        # FIXME: better response?
        msg = "Delete '%s' failed.\n%s" % traceback.format_exc()
        tlog.info(msg)
        raise HTTPBadRequest(text=msg)
        Pass
      pass
    # FIXME: better response?
    raise HTTPNotFound()
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
# Port for this HTTP server
cli.add_argument("-p", "--port", type=int, metavar="PORT", dest="port", default=8312)

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
arguments = cli.parse_args()

# If the module is invoked directly, initialize the application
if __name__ == '__main__':
  tlog = init_triage_logger(log_level=logging.DEBUG)
  
  # Create and configure the HTTP server instance
  the_root_url = u"{0}://{1}:{2}".format("http", arguments.host, arguments.port)

  # This is the default wce_share_url. 
  wce_share_url = u"{0}://{1}:{2}/wce".format("http", arguments.host, arguments.port)

  # Find a url share from boot cmdline. If this is nfs booted, it should be there.
  # Find payload as well
  wce_share_re = re.compile(const.wce_share + '=([\w\/\.+\-_\:\?\=@#\*&\\%]+)')
  wce_payload = None
  wce_payload_re = re.compile(const.wce_payload + '=([\w\.+\-_\:\?\=@#\*&\\%]+)')

  with open("/proc/cmdline") as cmdlinefd:
    cmdline = cmdlinefd.read()
    match = wce_share_re.search(cmdline)
    if match:
      wce_share_url = match.group(1)
      pass
    if not arguments.live_triage:
      match = wce_payload_re.search(cmdline)
      if match:
        wce_payload = match.group(1)
        pass
      pass
    pass

  # If wce_share is on the command line, override them all.
  if arguments.wce_share:
    wce_share_url = arguments.wce_share
    pass

  autoload = False
  load_disk_options = None
  
  if wce_payload:
    disk_image = None
    for disk_image in get_disk_images(wce_share_url):
      if disk_image['name'] == wce_payload:
        autoload = True
        break
      pass

    if autoload:
      load_disk_options = disk_image
      # translate the load option lingo here and web side
      # this could be unnecessary if I change the UI to match the both world
      load_disk_options['source'] = disk_image['fullpath']
      load_disk_options['restoretype'] = disk_image['restoreType']
      # size from get_disk_images comes back int, and web returns string.
      # going with string.
      load_disk_options['size'] = str(disk_image['size'])
      pass
    else:
      tlog.info("Payload {0} is requested but not autoloading as matching disk image does not exist.".format(wce_payload))
      wce_payload = None
      pass
    pass

  # Accept connection from everywhere
  tlog.info("Starting app.")

  global me
  wcedir = arguments.wcedir
  rootdir = arguments.rootdir
  if rootdir is None:
    rootdir = os.path.join(wcedir, "wce-triage-ui")
    pass
  # me = TriageWeb(app, wce_share_url, rootdir, wcedir, cors, loop, arguments.live_triage, load_disk_options)

  tlog.info(u"Open {0}{1} in a web browser. WCE share is {2}".format(the_root_url, "/<index.html", wce_share_url))
  # Emitter.register(loop)

  # aiohttp.web.run_app(app, host="0.0.0.0", port=arguments.port, access_log=get_triage_logger())

  socketio.run(app)
