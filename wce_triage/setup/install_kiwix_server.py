#!/usr/bin/python3
#
# Kiwix - offline wikipedia.
#
# Nothing runs until someone asks for it: kiwix-server-proxy.socket holds port
# 7777 on every interface, and the first connection - local or remote - starts
# the proxy, which starts kiwix-serve on loopback 17777.
#
import os, shutil, subprocess

SHARE_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'share', 'wce')
WCE_SHARE = '/usr/local/share/wce'
SYSTEMD_SRC = os.path.join(SHARE_SRC, 'lib', 'systemd', 'system')
SYSTEMD_SHARE = os.path.join(WCE_SHARE, 'lib', 'systemd', 'system')
CONTENT_DIR = os.path.join(WCE_SHARE, 'contents', 'wikipedia')

kiwix_bins = [
  "wce-kiwix-server",
  "wce-kiwix-wikipedia",
]

# Unit files to place. Only the socket is enabled - the two services are pulled
# in on demand, so enabling them would start kiwix at every boot.
kiwix_units = [
  "kiwix-server-proxy.socket",
  "kiwix-server-proxy.service",
  "kiwix-server.service",
]

enabled_units = [
  "kiwix-server-proxy.socket",
]


def run(argv):
  if os.getuid() != 0:
    argv = ['sudo', '-H'] + argv
    pass
  return subprocess.run(argv)


def install_kiwix_serve():
  """kiwix-serve comes from the kiwix-tools package. install_packages installs
  it for desktops, but this module also runs on its own."""
  if shutil.which('kiwix-serve'):
    return True
  run(['apt', 'install', '-y', '--no-install-recommends', 'kiwix-tools'])
  if shutil.which('kiwix-serve'):
    return True
  print("kiwix-serve is not available. Skipping kiwix server installation.")
  return False


def install_file(source, destination, mode):
  if not os.path.exists(source):
    print("Missing %s" % source)
    return False
  run(['install', '-D', '-m', mode, source, destination])
  return True


def install_systemd_file(unit):
  """The unit lives under /usr/local/share/wce and is linked into systemd."""
  if not install_file(os.path.join(SYSTEMD_SRC, unit),
                      os.path.join(SYSTEMD_SHARE, unit), '0644'):
    return False

  destination = os.path.join("/etc/systemd/system", unit)
  if not os.path.exists(destination):
    run(['ln', '-s', os.path.join(SYSTEMD_SHARE, unit), destination])
    pass
  return True


if __name__ == "__main__":
  if install_kiwix_serve():
    run(['mkdir', '-p', CONTENT_DIR])

    for filename in kiwix_bins:
      install_file(os.path.join(SHARE_SRC, 'bin', filename),
                   os.path.join('/usr/local/bin', filename), '0755')
      pass

    installed = [unit for unit in kiwix_units if install_systemd_file(unit)]

    run(['systemctl', 'daemon-reload'])

    for unit in enabled_units:
      if unit in installed:
        run(['systemctl', 'enable', unit])
        pass
      pass
    pass
  pass