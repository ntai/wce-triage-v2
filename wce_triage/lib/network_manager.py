import sys
import subprocess

def is_network_manager_on():
  netman = subprocess.run('systemctl status -n 0 NetworkManager.service', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  # No need to set up the netplan if Network Manager is available.
  # This means that it's running on a desktop machine with full Ubuntu installation
  return 'NetworkManager.service could not be found' not in netman.stderr.decode('iso-8859-1')


# generate netplan.yaml file for Network Manager to take over the network control
def generate_netplan_file_for_network_manager(filename = "/etc/netplan/01-network-manager-all.yaml"):
  """generate a netplan file from the devices' config for network manager."""
  if filename:
    output = open(filename, "w")
  else:
    output = sys.stdout
    pass
  lines = ["network:\n", "  version: 2\n", "  renderer: NetworkManager\n"]
  output.writelines(lines)
  if filename:
    output.close()
    pass
  pass


def connect_to_triage_wifi():
  nmcli = subprocess.Popen('nmcli dev wifi connect wcetriage password thepasswordiswcetriage', shell=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                           start_new_session=True)
  pass


if __name__ == "__main__":
    print( "Network manager: {}".format( "on" if is_network_manager_on() else "off") )
    print(generate_netplan_file_for_network_manager(filename=None))
    pass
