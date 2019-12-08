# WCE Triage

WCE Triage is a system of cloning disk images using multiple different media. The "triage" itself - cataloging the computer components is really a small part of WCE Triage. However it is a foundation of triage process and triage software.
Second part is to create the disk image from existing disk. "Save image" describes this.
Third part is to provision the disk image to local disk. This is simply called "Imaging disk".

Imaging disk can be done in multiple ways.
One is to load the disk image to local disks. For this, you can use any running Linux system. If you need to mass-produce pre-imaged disks, this is how. You connect a SATA disk dock and load disk images to many disks off-line.
Second is to use an external disk such as USB flash (aka USB sticks). For this, you need to start the computer from USB stick, and load. Typically, the USB stick has one disk image as the disk image tends to be large (20-45GB depending on the contents.) The contents is sometimes referred as "payload". 
Third is to similar to use external disk but instead of physical device, the computer boots over the network, and the installation server provides all necessary files over the network.
## Triage software overview
There are two major pieces. One is a HTTP server that runs on the computer  to manipulate the disk. In other word, in order to do any disk manipulation, the HTTP server has to be running. This is written in Python 3 using aiohttp.
Other is the web UI. This is written in React.JS. As this can run on any web browser, the browser doesn't have to be on the same machine as the HTTP server is running.
The HTTP server is the backend, and when a host computer starts, the HTTP server starts up by systemd. In other word, the http server is registered to systemd as a service, and it's name is "wce-triage.service".
To access the triage service over HTTP, you need the UI served by HTTP server. "Compiled" React.JS (static JavaScript) resides on the host, and it's location is at "/usr/local/share/wce/wce-triage-ui".
There is a third piece for the computer triaging. When the host starts, it needs a web browser. This means, it needs to run X11 server and web browser. Google Chrome and Chromium have "kiosk" mode, and the triage UI uses the kiosk mode to minimize the size used on disk. As these three needs to be on a USB stick, and fast, keeping the size small is important.
For the details of each, see the documentations in the source code.
