import sys
import socket
from argparse import ArgumentParser

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
