import os, subprocess, datetime, request
import urllib.request


def get_my_ip_address():
  ip_route = subprocess.run('ip route', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  return ip_route.stdout.decode('iso-8859-1').splitlines()[0].strip().split(' ')[8]
  
