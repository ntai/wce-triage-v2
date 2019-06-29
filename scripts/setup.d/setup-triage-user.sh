#!/bin/sh

if [ "x${TRIAGEUSER}" = "x" ] ; then
    TRIAGEUSER=triage
fi

# Be able to start the tty by user
sudo usermod -a -G tty,audio,video $TRIAGEUSER

# and, be able to start X by user
sudo chmod ug+s /usr/lib/xorg/Xorg
