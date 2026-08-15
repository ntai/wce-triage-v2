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
from .version import TRIAGE_VERSION

name = "wce_triage"

# Semi-standard module versioning.
__version__ = TRIAGE_VERSION

debian_package_dependencies = (
    'partclone',     # partclone is a part of Clonezilla
    'pigz',          # parallel gzip
    'gnupg',         # apt-ftparchive
    'dmidecode',     # dpkg-architecture
    'grub2-common',  # 
    'grub2-pc',      # 
    'efibootmgr',    # 
    'alsa-utils',    #
    # No audio server here. The sound test streams the file to the browser and
    # the browser plays it - see api/routers/dispatch.py route_music - so this
    # package needs no pulseaudio/pipewire/pactl of its own. Requiring
    # 'pulseaudio' actively broke 24.04/26.04: it conflicts with pipewire-audio
    # and takes the desktop metapackages out with it.
    # No python packages here. The server is fastapi + uvicorn now, not
    # aiohttp, and it runs out of a venv - see pyproject.toml. System python
    # packages are not on that path, so listing them installs dead weight.
)
"""A tuple of strings with required Debian packages."""


def generate_stdeb_cfg() -> None:
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
