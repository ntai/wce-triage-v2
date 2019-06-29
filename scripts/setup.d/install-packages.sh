#!/bin/sh
#
# Install Ubunto packages (some are python packages)
#
# xorg-legacy asks you to run x server user credential and it needs to run as root.
#
apt remove -y apparmor

#
# xserver-xorg-legacy - Ubuntu 18.04LTS needs to run X11 server as root. Setting video mode requires the root priv.
#   This may change in future. Also, this pops up a dialog. If you see it, choose "everyone".
#
sudo apt install -y xserver-xorg-legacy
#
# aufs-tools - for making usb stick to boot and mount memory file system as read/write over read-only usb storage
# python3-pip - bootstrapping pip3.
# dmidecode - essentail to see the memory configurations.
# partclone - to save/load partition
# efibootmgr - EFI-boot is not supported yet. Will come.
# grub2-common, grub-pc - boot loader
# pigz - parallel gzip
# vbetool - video buffer tool
# gfxboot - pretty boot screen
# alsa-utils pulseaudio pulseaudio-utils mpg123 - the audio. mpg123 is no longer used but included. mpg123 plays mp3 from console
# python3-aiohttp python3-aiohttp-cors - triage backend. yes, you can cross-domain
#
for pkg in xorg openbox aufs-tools python3-pip xserver-xorg-video-all xserver-xorg-video-vmware gnupg dmidecode partclone efibootmgr grub2-common grub-pc pigz vbetool gfxboot alsa-utils pulseaudio pulseaudio-utils mpg123 python3-aiohttp python3-aiohttp-cors; do
    sudo apt install -y --no-install-recommends $pkg
done

#
# install python packages.
#  Why not use pip3? Ubuntu server is far more stable than pypi server.
#  Also, the packages on pypi moves too fast and dependencies can be a headache.
#
# python-socketio - websocket.
#
for pkg in python-socketio; do
    sudo pip3 install $pkg
done
