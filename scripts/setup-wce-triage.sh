#!/bin/sh

export GRUB_DISABLE_OS_PROBER=true
export TRIAGEUSER=triage
export WCE_TRIAGE_DISK=true

# Create triage account
setup.d/setup-triage-user.sh

# Install Ubunto packages (some are python packages)
setup.d/install-packages.sh

# Install Google Chrome
setup.d/install-chrome.sh

# Install Triage software
setup.d/install-assets.sh

sudo setup.d/patch-system

# Install triage services
setup.d/install-wce-kiosk.sh
setup.d/install-wce-triage.sh

# boot loader installation
setup.d/setup-boot.sh
