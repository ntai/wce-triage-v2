#!/usr/bin/python3
import os, sys, subprocess

stem = ['sudo', '-H', 'lighty-enable-mod']

for mod in ['cgi', 'dir-listing', 'flv-streaming', 'rewrite']:
    subprocess.run(stem + [mod])
    pass

if not os.path.exists("/var/www/html/wce"):
    subprocess.run("ln -s /usr/local/share/wce /var/www/html/wce")
    pass
