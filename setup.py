import setuptools, sys, os

with open("README.rst", "r") as fh:
  long_description = fh.read()

# The wce triage is designed to work with Ubuntu 18.04LTS and after
# that comes with Python 3.6.
#
# The wce triage is designed to work with Ubuntu 20.04LTS and after
# that comes with Python 3.8.
python_version = sys.version_info
need_python_version = (3, 8)

if python_version < need_python_version:
  raise RuntimeError("wce_triage requires Python version %d.%d or higher"
                     % need_python_version)

sys.path.append(os.getcwd())
from wce_triage.version import *

setuptools.setup(
  name="wce_triage",
  version=TRIAGE_VERSION,
  author="Naoyuki Tai",
  author_email="ntai@cleanwinner.com",
  description="WCE Triage",
  long_description=long_description,
  long_description_content_type="text/markdown",
  url="https://github.com/ntai/wce-triage-v2",
  packages=['wce_triage',
            'wce_triage.backend',
            'wce_triage.bin',
            'wce_triage.components',
            'wce_triage.lib',
            'wce_triage.http',
            'wce_triage.ops',
            'wce_triage.setup'],
  include_package_data=True,
  install_requires=[
    'aiohttp==3.6.2',
    'aiohttp-cors==0.7.0',
    'Flask==3.0.0',
    'Flask-CLI==0.4.0',
    'Flask-Cors==3.0.10',
    'Flask-SocketIO==5.3.3',
    'python-engineio==4.8.1',
    'python-socketio==5.10.0',
    'typing_extensions==4.9.0',
  ],
  classifiers=[
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX :: Linux",
  ],
)

