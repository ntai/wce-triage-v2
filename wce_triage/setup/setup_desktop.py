#!/usr/bin/python3

import os, sys

os.environ['GRUB_DISABLE_OS_PROBER'] = 'true'
os.environ['TRIAGEUSER'] = 'wce'
os.environ['WCE_DESKTOP'] = 'true'

# Install Ubunto packages (some are python packages)

import wce_triage.setup.install_packages

# Install Triage software
import wce_triage.setup.install_assets

# Install triage runner
import wce_triage.setup.install_wce_triage

