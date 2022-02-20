"""
The MIT License (MIT) Copyright (c) 2022 - Naoyuki Tai

cli.py: WCE http server command line interface
"""
#
#
#
import os
# from argparse import ArgumentParser
#
# cli = ArgumentParser(description='Triage web server')
# # Port for this HTTP server
# cli.add_argument("-p", "--port", type=int, metavar="PORT", dest="port", default=8400)
#
# # And it's hostname. It's usually the local host FQDN but, as the client's DNS may not work reliably,
# # you need to be able to set this sometimes.
# cli.add_argument("--host", type=str, metavar="HOST", dest="host", default=socket.getfqdn())
#
# # Location of UI assets.
# cli.add_argument("--rootdir", type=str, metavar="WCE_TRIAGE_UI_ROOTDIR", dest="rootdir", default=None)
#
# # This is where disk images live
# cli.add_argument("--wcedir", type=str, metavar="WCE_ROOT_DIR", dest="wcedir", default="/usr/local/share/wce")
#
# # If you want to use other server (any other http server) you need to override this.
# # This is necessary if you want to offload the payload download to web server light apache.
# # For this case, you need to be able to use any URL.
# # Note that, the boot arg (aka cmdline) is used for picking up the default value of wce_share_url
# # as well, and this overrides this.
# cli.add_argument("--wce_share", type=str, metavar="WCE_SHARE_URL", dest="wce_share", default=None)
#
# cli.add_argument("--live-triage", dest="live_triage", action='store_true')
# # arguments = cli.parse_args(sys.argv[2:])

class Config(object):
  """Base configuration."""

  HOST = 'localhost'
  PORT = 8400

  PROPAGATE_EXCEPTIONS = False
  SECRET_KEY = os.environ.get('CONDUIT_SECRET', 'secret-key')  # TODO: Change me
  APP_DIR = os.path.abspath(os.path.dirname(__file__))  # This directory
  PROJECT_ROOT = os.path.abspath(os.path.join(APP_DIR, os.pardir))
  BCRYPT_LOG_ROUNDS = 13
  DEBUG_TB_INTERCEPT_REDIRECTS = False
  CACHE_TYPE = 'simple'  # Can be "memcached", "redis", etc.
  SQLALCHEMY_TRACK_MODIFICATIONS = False
  JWT_AUTH_USERNAME_KEY = 'email'
  JWT_AUTH_HEADER_PREFIX = 'Token'
  CORS_ORIGIN_WHITELIST = [
    'http://0.0.0.0:8080',
    'http://localhost:8080',
    'http://0.0.0.0:8400',
    'http://localhost:8400',
    'http://0.0.0.0:80',
    'http://localhost:80',
    'http://0.0.0.0:4000',
    'http://localhost:4000',
  ]
  JWT_HEADER_TYPE = 'Token'

  WCEDIR = None
  # Location of UI assets.
  TRIAGE_UI_ROOTDIR = None

  # URL for wce share. This cuold point to different endpoint (eg, disk image server)
  WCE_SHARE_URL = None

  LIVE_TRIAGE = False


class DevConfig(Config):
  """Development configuration."""
  ENV = 'dev'
  DEBUG = True
  pass


class ProdConfig(Config):
  """Production configuration."""
  ENV = 'prod'
  DEBUG = True
