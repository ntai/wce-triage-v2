#!/bin/sh

rm /swapfile

export TRIAGE_SSID=wcetriage
export TRIAGE_PASSWORD=thepasswordiswcetriage
export PYTHONPATH=$PWD/wce-triage-v2

python3 wce-triage-v2/wce_triage/bin/start_network.py
sudo apt install -y python3-pip
sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage

apt purge g++-7
apt purge wamerican wbritish
apt purge manpages-dev

apt purge linux-headers-generic
apt purge linux-headers-4.15.0-52
linux-headers-4.15.0-52-generic
