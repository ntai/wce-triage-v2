#!/usr/bin/python3

import os, json, re
from ..lib.util import  *


if __name__ == "__main__":

  peeraddr, myaddr = get_ip_addresses()
  myport = get_lighttpd_server_port()

  sources = []
  url_template = 'http://{myaddr}:{myport}/wce-disk-images/{restoretype}/{filename}'
  for source in get_disk_images():
    source['url'] = url_template.format(myaddr=myaddr, myport=myport, restoretype=source['restoreType'], filename=source['name'])
    sources.append(source)
    pass

  listfile = open('/usr/local/share/wce/wce-disk-images/wce-disk-images.json', 'w')
  json.dump({ "sources": sources }, listfile)
  pass
