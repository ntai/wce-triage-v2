#!/bin/sh

export GRUB_DISABLE_OS_PROBER=true
export TRIAGEUSER=triage

# Install Ubunto packages (some are python packages)
setup.d/install-packages.sh

# Install Google Chrome
setup.d/install-chrome.sh

# Install Triage software
setup.d/install-assets.sh

sudo setup.d/patch-system

# Install triage services
setup.d/install-services.sh


# boot loader installation
setup.d/setup-boot.sh
