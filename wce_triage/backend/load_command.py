from .messages import UserMessages
from .models import Model, ModelDispatch
from .process_runner import SimpleProcessRunner
from ..lib.disk_images import read_disk_image_types
from ..lib.util import get_triage_logger
from ..components.disk import PartitionLister
from .server import server
from http import HTTPStatus


tlog = get_triage_logger()
#
#
#

def foo():
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


class LoadCommandRunner(SimpleProcessRunner):

  # Since ProcessRunner is generic, there is not much reason to make this "Load" only but by limiting one thread
  # to run particular command, it's serializied.

  def __init__(self, dispatch: ModelDispatch):
    super().__init__(stdout_dispatch=dispatch, meta = {"tag": "loadimage"})
    pass

  def queue_load(self, devname, imagefile, wipe_request, newhostname):
    args = ['python3', '-m', 'wce_triage.ops.restore_image_runner', devname]

    if newhostname:
      args.append('-m')
      args.append(newhostname)
      pass

    wipe = None
    for wipe_type in WIPE_TYPES:
      if wipe_type.get("id") == wipe_request:
        args.append(wipe_type.get("arg"))
        break
      pass

    target = None
    for disk in server.disk_portal.disks:
      if disk.device_name == devname:
        target = disk
        break
      pass

    if target is None:
      tlog.info("No such disk " + devname)
      return {}, HTTPStatus.BAD_REQUEST

    disk = server.disk_portal.find_disk_by_device_name(devname)

    # loadType is a single word coming back from read_disk_image_types()
    image_type = None
    for _type in read_disk_image_types():
      if _type["id"] == loadType:
        image_type = _type
        break
      pass

    if image_type is None:
      UserMessages.error("Image type %s is not known." % loadType)
      return {}, HTTPStatus.BAD_REQUEST

    destdir = image_type.get('catalogDirectory')
    if destdir is None:
      msg = UserMessages.error("Imaging type info %s does not include the catalog directory." % image_type.get("id"))
      return {"message": msg}, HTTPStatus.BAD_REQUEST

    # Load image runs its own course, and output will be monitored by a call back
    self.queue(args, {"args": args, "devname": devname, "imagefile": imagefile, "wipe": wipe, "newhostname": newhostname })
    return {}, HTTPStatus.OK

  pass


