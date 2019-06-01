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

CHUNK_SIZE = 4096
HTTP_STATUS = {"OK": ResponseStatus(code=200, message="OK"),
               "BAD_REQUEST": ResponseStatus(code=400, message="Bad request"),
               "NOT_FOUND": ResponseStatus(code=404, message="Not found"),
               "INTERNAL_SERVER_ERROR": ResponseStatus(code=500, message="Internal server error")}
PROTOCOL = "http"


def make_bytestream(data):
  json_data = dumps(data)
  print(json_data)
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
    self.routes = { "/index.html": self.route_index,
                    "/triage.json": self.route_triage,
                    "/disks.json": self.route_disks,
                    "/disk-images.json": self.route_disk_images,
                    "/load": self.route_load_image,
                    "/save": self.route_save_image
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

    try:
      # Handle the possible request paths
      if handler:
        response = handler(path, query)
      else:
        response = self.route_404(path, query)
        pass

      self.send_headers(response.status, response.content_type)
      self.stream_data(response.data_stream)

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

      print("[END]")
      pass
    pass

  def route_404(self, path, query):
    """Handles routing for unexpected paths"""
    raise HTTPStatusError(HTTP_STATUS["NOT_FOUND"], "Page not found")

  def route_index(self, path, query):
    """Handles routing for the application's entry point'"""
    try:
      # Open a binary stream for reading the index HTML file
      return ResponseData(status=HTTP_STATUS["OK"], content_type="text_html",
                          data_stream=open(os.path.join(sys.path[0],
                                                        path[1:]), "rb"))
    except IOError as err:
      # Couldn't open the stream
      raise HTTPStatusError(HTTP_STATUS["INTERNAL_SERVER_ERROR"], str(err))
    pass


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
      self.overall_decision = self.computer.triage()
      pass

    # decision comes back as tuple, make it to the props for jsonify
    jsonified = { "components": [ {"component": component, "result": "Good" if good else "Bad", "details": dtl} for component, good, dtl in self.computer.decisions ] }
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

    disks = [ {"device": disk.device_name,
               "disk": "y" if disk.is_disk else "n",
               "mounted": "y" if disk.mounted else "n",
               "bus": "usb" if disk.is_usb else "ata",
               "model": disk.disk_model }
              for disk in self.computer.disks ]

    return ResponseData(status=HTTP_STATUS["OK"],
                        content_type="application/json",
                        data_stream=make_bytestream(disks))
    pass


  def route_disk_images(self, path, query):
    """Handles getting the list of disk images"""

    images = get_disk_images()
    return ResponseData(status=HTTP_STATUS["OK"],
                        content_type="application/json",
                        data_stream=make_bytestream(images.keys()))
    pass


  def route_load_image(self, path, query):
    """Load disk image to disk"""

    return ResponseData(status=HTTP_STATUS["OK"],
                        content_type="application/json",
                        data_stream=make_bytestream("HELLO!"))
    pass

  def route_save_image(self, path, query):
    """Load disk image to disk"""

    return ResponseData(status=HTTP_STATUS["OK"],
                        content_type="application/json",
                        data_stream=make_bytestream(""))
    pass


  def stream_data(self, stream):
    """Consumes a stream in chunks to produce the response's output'"""
    print("Streaming started...")

    if stream:
      # Note: Closing the stream is important as the service throttles on
      # the number of parallel connections. Here we are using
      # contextlib.closing to ensure the close method of the stream object
      # will be called automatically at the end of the with statement's
      # scope.
      with closing(stream) as managed_stream:
        # Push out the stream's content in chunks
        while True:
          data = managed_stream.read(CHUNK_SIZE)
          # self.wfile.write(b"%X\r\n%s\r\n" % (len(data), data))
          self.wfile.write(b"%s\r\n" % (data))

          # If there's no more data to read, stop streaming
          if not data:
            break
          pass

        # Ensure any buffered output has been transmitted and close the
        # stream
        self.wfile.flush()
        pass

      print("Streaming completed.")
    else:
      # The stream passed in is empty
      self.wfile.write(b"\r\n\r\n")
      print("Nothing to stream.")
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
cli.add_argument("--host", type=str, metavar="HOST", dest="host", default="0.0.0.0")
arguments = cli.parse_args()

# If the module is invoked directly, initialize the application
if __name__ == '__main__':
  # Create and configure the HTTP server instance
  server = ThreadedHTTPServer((arguments.host, arguments.port), TriageHTTPRequestHandler)
  print("Starting server, use <Ctrl-C> to stop...")
  weburl = u"{0}://{1}:{2}{3}".format(PROTOCOL,
                                      arguments.host,
                                      arguments.port,
                                      "/index.html")
  print(u"Open {0} in a web browser.".format(weburl))
  subprocess.call(["x-www-browser", weburl])
  try:
    # Listen for requests indefinitely
    server.serve_forever()
  except KeyboardInterrupt:
    # A request to terminate has been received, stop the server
    print("\nShutting down...")
    server.socket.close()
    pass
  pass

