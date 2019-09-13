# WCE Triage
#
# Author: Naoyuki Tai
# Last Change: Jul, 2019
# URL: https://github.com/ntai/wce-triage-v2

"""
The top-level :mod:`deb_pkg_tools` module.

The :mod:`deb_pkg_tools` module defines the `deb-pkg-tools` version number and
the Debian packages that are required to use all of the features provided by
the `deb-pkg-tools` package.
"""
name = "wce_triage"

from .version import *

# Semi-standard module versioning.
__version__ = TRIAGE_VERSION

debian_package_dependencies = (
    'partclone',     # partclone is a part of Clonezilla
    'pigz' ,         # parallel gzip
    'gnupg',         # apt-ftparchive
    'dmidecode',     # dpkg-architecture
    'grub2-common',  # 
    'grub2-pc',      # 
    'efibootmgr',    # 
    'alsa-utils',    # 
    'pulseaudio',    #
    'pulseaudio-utils',     #
    'python3-aiohttp',      #
    'python3-aiohttp-cors', #
)
"""A tuple of strings with required Debian packages."""


def generate_stdeb_cfg():
    """
    Generate the contents of the ``stdeb.cfg`` file used by stdeb_ and py2deb_.

    The Debian package dependencies and minimal Python version are included in
    the output.

    .. _stdeb: https://pypi.python.org/pypi/stdeb
    .. _py2deb: https://pypi.python.org/pypi/py2deb
    """
    print('[wce_triage]')
    print('Depends: ')
    print('Recommends: %s' % ', '.join(pkg for pkg in debian_package_dependencies if pkg != 'python-apt'))
    print('Suggests: ')
