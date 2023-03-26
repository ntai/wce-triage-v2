#!/bin/bash
sudo -H apt install -y python3-pip --no-install-recommends
sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage
python3 -m wce_triage.setup.setup_triage_system
