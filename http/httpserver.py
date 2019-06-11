""" 
WCE Triage HTTP server - 

(supports Python 2.7+/3.3+ just because)

"""
from argparse import ArgumentParser
from collections import namedtuple
from contextlib import closing
from json import dumps
import os
import sys
import mimetypes
import socket
mimetypes.add_type("text/css", ".less")

if sys.version_info >= (3, 0):
  from http.server import BaseHTTPRequestHandler, HTTPServer
  from socketserver import ThreadingMixIn
  from urllib.parse import parse_qs
  from io import StringIO
  from io import BytesIO
else:
  from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
  from SocketServer import ThreadingMixIn
  from urlparse import parse_qs
  from StringIO import StringIO
  pass

import subprocess

from components.computer import Computer

ResponseStatus = namedtuple("HTTPStatus", ["code", "message"])
ResponseData = namedtuple("ResponseData", ["status", "content_type", "data_stream"])
Redirect = namedtuple("Redirect", ["url"])

CHUNK_SIZE = 4096
HTTP_STATUS = {"OK": ResponseStatus(code=200, message="OK"),
               "BAD_REQUEST": ResponseStatus(code=400, message="Bad request"),
               "NOT_FOUND": ResponseStatus(code=404, message="Not found"),
               "INTERNAL_SERVER_ERROR": ResponseStatus(code=500, message="Internal server error")}
PROTOCOL = "http"


def make_bytestream(data):
  json_data = dumps(data)
  return BytesIO(bytes(json_data, "utf-8") if sys.version_info >= (3, 0) else bytes(json_data))


class HTTPStatusError(Exception):
  """Exception wrapping a value from http.server.HTTPStatus"""

  def __init__(self, status, description=None):
    """
    Constructs an error instance from a tuple of
    (code, message, description), see http.server.HTTPStatus
    """
    super(HTTPStatusError, self).__init__()
    self.code = status.code
    self.message = status.message
    self.explain = description
    pass
  pass


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
  """An HTTP Server that handle each request in a new thread"""
  daemon_threads = True
  pass


class TriageHTTPRequestHandler(BaseHTTPRequestHandler):
  """"HTTP 1.1 Triage encoding request handler"""
  # Use HTTP 1.1 as 1.0 doesn't support triage encoding
  protocol_version = "HTTP/1.1"

  def __init__(self, *argv):
    """
    HTTP request handler for triage
    """
    self.routes = { "/": self.route_root,
                    "/index.html": self.route_index,
                    "/dispatch/triage.json": self.route_triage,
                    "/dispatch/disks.json": self.route_disks,
                    "/dispatch/disk-images.json": self.route_disk_images,
                    "/dispatch/disk-load-status.json": self.route_disk_load_status,
                    "/dispatch/load": self.route_load_image,
                    "/dispatch/save": self.route_save_image
    }

    self.computer = Computer()
    self.overall_decision = None
    super(BaseHTTPRequestHandler, self).__init__(*argv)
    pass

  def query_get(self, queryData, key, default=""):
    """Helper for getting values from a pre-parsed query string"""
    return queryData.get(key, [default])[0]

  def do_GET(self):
    """Handles GET requests"""

    # Extract values from the query string
    path, _, query_string = self.path.partition('?')
    query = parse_qs(query_string)

    response = None

    print(u"[START]: Received GET for %s with query: %s" % (path, query))

    handler = self.routes.get(path)
    if handler is None:
      filepath = os.path.join(rootdir, path[1:])
      handler = self.route_static_file if os.path.exists(filepath) and os.path.isfile(filepath) else self.route_404
      pass

    try:
      # Handle the possible request paths
      response = handler(path, query)
      if isinstance(response, ResponseData):
        self.send_headers(response.status, response.content_type)
        self.stream_data(response.data_stream)
      elif isinstance(response, Redirect):
        self.send_response(301)
        self.send_header('Transfer-Encoding', 'utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Location', response.url)
        self.end_headers()
        pass
      elif response is None:
        raise Exception("Response is None. You bonehead!")
      else:
        raise Exception("Unknown response")
      pass
    except HTTPStatusError as err:
      # Respond with an error and log debug
      # information
      if sys.version_info >= (3, 0):
        self.send_error(err.code, err.message, err.explain)
      else:
        self.send_error(err.code, err.message)
        pass
      self.log_error(u"%s %s %s - [%d] %s", self.client_address[0],
                     self.command, self.path, err.code, err.explain)
      pass

    print("[END]")
    pass


  def route_404(self, path, query):
    """Handles routing for unexpected paths"""
    raise HTTPStatusError(HTTP_STATUS["NOT_FOUND"], "Page not found")

  def route_static_file(self, path, query):
    """Handles routing for a file'"""

    ctype = mimetypes.guess_type(path)[0]
    if ctype is None:
      ctype  = "text"
      pass
    try:
      # Open a binary stream for reading a file
      return ResponseData(status=HTTP_STATUS["OK"], content_type=ctype,
                          data_stream=open(os.path.join(rootdir, path[1:]), "rb"))
    except IOError as err:
      # Couldn't open the stream
      raise HTTPStatusError(HTTP_STATUS["INTERNAL_SERVER_ERROR"], str(err))
    pass

  def route_root(self, path, query):
    """Redirect / to index.html"""
    global the_root_url
    print(u"Redirecting to {0} in a web browser.".format(the_root_url))
    return Redirect(the_root_url)

  def route_index(self, path, query):
    """Handles routing for the application's entry point'"""
    return self.route_static_file(path, query)

  def route_triage(self, path, query):
    """Handles requesting traige result"""
    
    if self.overall_decision is None:
      try:
        self.overall_decision = self.computer.triage()
        pass
      except (ClientError) as err:
        # The service returned an error
        raise HTTPStatusError(HTTP_STATUS["INTERNAL_SERVER_ERROR"],
                              str(err))
      pass

    # decision comes back as tuple, make it to the props for jsonify
    jsonified = { "components": [ {"component": thing, "result": "Good" if good else "Bad", "details": dtl} for thing, good, dtl in self.computer.decisions ] }
    return ResponseData(status=HTTP_STATUS["OK"],
                        content_type="application/json",
                        data_stream=make_bytestream(jsonified))


  def route_disks(self, path, query):
    """Handles getting the list of disks"""

    if self.overall_decision is None:
      try:
        self.overall_decision = self.computer.triage()
        pass
      except (ClientError) as err:
        # The service returned an error
        raise HTTPStatusError(HTTP_STATUS["INTERNAL_SERVER_ERROR"],
                              str(err))
      self.overall_decision = self.computer.triage()
      pass

    
    disks = [ {"target": 0,
               "progress": 0,
               "elapseTime": 0,
               "device": disk.device_name,
               "disk": "y" if disk.is_disk else "n",
               "mounted": "y" if disk.mounted else "n",
               "bus": "usb" if disk.is_usb else "ata",
               "model": disk.disk_model }
              for disk in self.computer.disks ]

    jsonified = { "diskPages": 1, "disks": disks }

    return ResponseData(status=HTTP_STATUS["OK"],
                        content_type="application/json",
                        data_stream=make_bytestream(jsonified))
    pass


  def route_disk_images(self, path, query):
    """Handles getting the list of disk images"""

    # images = get_disk_images()
    images = { "sources": [
      { "mtime": "2019-04-01", "name": "wce-1.tar.gz", "fullpath": "/var/www/wce-1.tar.gz", "size": 1001 },
      { "mtime": "2019-04-02", "name": "wce-2.tar.gz", "fullpath": "/var/www/wce-2.tar.gz", "size": 1002 },
      { "mtime": "2019-04-03", "name": "wce-3.tar.gz", "fullpath": "/var/www/wce-3.tar.gz", "size": 1003 }
      ]}

    return ResponseData(status=HTTP_STATUS["OK"],
                        content_type="application/json",
                        data_stream=make_bytestream(images))
    pass


  def route_load_image(self, path, query):
    """Load disk image to disk"""

    fake_status = { "pages": 1,
                    "sources": [ "wce-1.tar.gz", "wce-2.tar.gz", "wce-3.tar.gz" ] }

    return ResponseData(status=HTTP_STATUS["OK"],
                        content_type="application/json",
                        data_stream=make_bytestream(fake_status))
    pass

  def route_disk_load_status(self, path, query):
    """Load disk image to disk"""

    fake_status = { "pages": 1,
                    "steps": [ { "category": "Step-1", "progress": 100, "elapseTime": "100", "status": "done" },
                               { "category": "Step-2", "progress": 30, "elapseTime": "30", "status": "running" },
                               { "category": "Step-3", "progress": 0, "elapseTime": "0", "status": "waiting" },
                               { "category": "Step-4", "progress": 0, "elapseTime": "0", "status": "waiting" } ] }

    return ResponseData(status=HTTP_STATUS["OK"],
                        content_type="application/json",
                        data_stream=make_bytestream(fake_status))
    pass

  def route_save_image(self, path, query):
    """Load disk image to disk"""

    return ResponseData(status=HTTP_STATUS["OK"],
                        content_type="application/json",
                        data_stream=make_bytestream(""))
    pass


  def stream_data(self, stream):
    """Consumes a stream in chunks to produce the response's output'"""
    if stream:
      # Note: Closing the stream is important as the service throttles on
      # the number of parallel connections. Here we are using
      # contextlib.closing to ensure the close method of the stream object
      # will be called automatically at the end of the with statement's
      # scope.
      with closing(stream) as managed_stream:
        # Push out the stream's content in chunks
        streaming = True
        while streaming:
          data = managed_stream.read(CHUNK_SIZE)
          # If there's no more data to read, stop streaming
          try:
            if not data:
              streaming = False
              self.wfile.write(b"\r\n")
              break
            self.wfile.write(b"%s" % (data))
          except BrokenPipeError as exc:
            # The receiving end stopped accepting data.
            streaming = False
            pass
          except Exception as exc:
            raise exc
          pass

        # Ensure any buffered output has been transmitted and close the
        # stream
        self.wfile.flush()
        pass
    else:
      # The stream passed in is empty
      self.wfile.write(b"\r\n\r\n")
      pass
    pass

  def send_headers(self, status, content_type):
    """Send out the group of headers for a successful request"""
    # Send HTTP headers
    self.send_response(status.code, status.message)
    self.send_header('Content-type', content_type)
    self.send_header('Transfer-Encoding', 'utf-8')
    self.send_header('Connection', 'close')
    self.send_header('Access-Control-Allow-Origin', '*')
    self.end_headers()
    pass

  pass

# Define and parse the command line arguments
cli = ArgumentParser(description='Example Python Application')
cli.add_argument("-p", "--port", type=int, metavar="PORT", dest="port", default=8312)
cli.add_argument("--host", type=str, metavar="HOST", dest="host", default=socket.getfqdn())
cli.add_argument("--rootdir", type=str, metavar="ROOTDIR", dest="rootdir", default=os.getcwd())
arguments = cli.parse_args()

# If the module is invoked directly, initialize the application
if __name__ == '__main__':
  # Create and configure the HTTP server instance
  global the_root_url
  the_root_url = u"{0}://{1}:{2}{3}".format(PROTOCOL,
                                            arguments.host,
                                            arguments.port,
                                            "/index.html")
  rootdir = arguments.rootdir
  # Accept connection from everywhere
  server = ThreadedHTTPServer(('0.0.0.0', arguments.port), TriageHTTPRequestHandler)
  print("Starting server, use <Ctrl-C> to stop...")
  print(u"Open {0} in a web browser.".format(the_root_url))
  try:
    # Listen for requests indefinitely
    server.serve_forever()
  except KeyboardInterrupt:
    # A request to terminate has been received, stop the server
    print("\nShutting down...")
    server.socket.close()
    pass
  pass

