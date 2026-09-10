#!/usr/bin/python3
import os, shutil, subprocess

if not shutil.which("nginx"):
    exit(0)

# nginx has no lighty-enable-mod equivalent - there's no runtime "enable a
# module" command. dir-listing (autoindex) and rewrite are directives inside
# the site config itself (see patches/.../etc/nginx/sites-available/
# default.diff), not something a setup script switches on. cgi isn't
# supported by nginx at all, and isn't needed here - wce-triage serves
# everything through FastAPI/uvicorn now, not CGI scripts.

if not os.path.exists("/var/www/html/wce"):
    subprocess.run("ln -s /usr/local/share/wce /var/www/html/wce", shell=True)
    pass