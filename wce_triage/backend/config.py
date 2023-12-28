"""
The MIT License (MIT) Copyright (c) 2022 - Naoyuki Tai

cli.py: WCE http server command line interface
"""
#
#
#
import re
# from argparse import ArgumentParser

from wce_triage.const import const
from wce_triage.lib import get_triage_logger
from wce_triage.lib.disk_images import get_disk_images

class Config(object):
  """Base configuration."""
  # Flask app configuration
  PROPAGATE_EXCEPTIONS = False
  CORS_ORIGIN_WHITELIST = [
    'http://0.0.0.0:10600',
    'http://localhost:10600',
    'http://0.0.0.0:8080',
    'http://localhost:8080',
    'http://0.0.0.0:8400',
    'http://localhost:8400',
    'http://0.0.0.0:80',
    'http://localhost:80',
    'http://0.0.0.0:4000',
    'http://localhost:4000',
  ]

  # Triage app stuff
  HOST = '0.0.0.0'
  PORT = '10600'
  WCEDIR = "/usr/local/share/wce"
  TRIAGE_UI_ROOTDIR = "/usr/local/share/wce/wce-triage-ui"
  WCE_SHARE_URL = "/usr/local/share/wce"
  LIVE_TRIAGE = False
  PAYLOAD = None
  LOAD_DISK_OPTIONS = None

  @staticmethod
  def cmdline():

    # Find a url share from boot cmdline. If this is nfs booted, it should be there.
    # Find payload as well
    wce_share_re = re.compile(const.wce_share + '=([\w\/\.+\-_\:\?\=@#\*&\\%]+)')
    wce_payload_re = re.compile(const.wce_payload + '=([\w\.+\-_\:\?\=@#\*&\\%]+)')

    with open("/proc/cmdline") as cmdlinefd:
      cmdline = cmdlinefd.read()
      match = wce_share_re.search(cmdline)
      if match:
        Config.WCE_SHARE_URL = match.group(1)
        pass
      match = wce_payload_re.search(cmdline)
      if match:
        Config.PAYLOAD = match.group(1)
        pass
      pass

  def dead_argparse(self):
    # cli = ArgumentParser(description='Triage App')
    # # Port for this HTTP server
    # cli.add_argument("-p", "--port", type=int, metavar="PORT", dest="port", default=Config.PORT)
    #
    # # And it's hostname. It's usually the local host FQDN but, as the client's DNS may not work reliably,
    # # you need to be able to set this sometimes.
    # cli.add_argument("--host", type=str, metavar="HOST", dest="host", default=socket.getfqdn())
    #
    # # Location of UI assets.
    # cli.add_argument("--rootdir", type=str, metavar="WCE_TRIAGE_UI_ROOTDIR", dest="rootdir",
    #                  default=Config.TRIAGE_UI_ROOTDIR)
    #
    # # This is where disk images live
    # cli.add_argument("--wcedir", type=str, metavar="WCE_ROOT_DIR", dest="wcedir",
    #                  default=Config.WCEDIR)
    #
    # # This is necessary if you want to offload the payload download to web server.
    # # For this case, you need to be able to use any URL.
    # # Note that, the boot arg (aka cmdline) is used for picking up the default value of wce_share_url
    # # as well, and this overrides this.
    # cli.add_argument("--wce_share", type=str, metavar="WCE_SHARE_URL", dest="wce_share",
    #                  default=Config.WCE_SHARE_URL)
    # cli.add_argument("--payload", dest="payload", default=Config.PAYLOAD)
    #
    # cli.add_argument("--live-triage", dest="live_triage", action='store_true', default=False)
    #
    # #arguments = cli.parse_args()
    # #known = cli.parse_known_args()
    #
    #
    # # No way to do auto load with live triage
    # if arguments.live_triage:
    #   Config.PAYLOAD = None
    #   pass
    #
    pass

  @staticmethod
  def check_auto_load():
    tlog = get_triage_logger()
    autoload = False
    if Config.PAYLOAD:
      disk_image = None
      for disk_image in get_disk_images(Config.WCEDIR):
        if disk_image['name'] == Config.PAYLOAD:
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
        Config.LOAD_DISK_OPTIONS = load_disk_options
        pass
      else:
        tlog.info(
          "Payload {0} is requested but not autoloading as matching disk image does not exist.".format(Config.PAYLOAD))
        pass
      pass
    pass


class DevConfig(Config):
  """Development configuration."""
  ENV = 'dev'
  DEBUG = True
  pass


class ProdConfig(Config):
  """Production configuration."""
  ENV = 'prod'
  DEBUG = True
