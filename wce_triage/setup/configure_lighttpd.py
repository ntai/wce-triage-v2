#!/usr/bin/python3
import os, sys, subprocess

stem = ['sudo', '-H', 'lighty-enable-mod']

for mod in ['cgi', 'dir-listing', 'flv-streaming', 'rewrite']:
    subprocess.run(stem + [mod])
    pass
