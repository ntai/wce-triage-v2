#!/bin/sh

export GRUB_DISABLE_OS_PROBER=true
export TRIAGEUSER=wce
export WCE_DESKTOP=true

# Install Ubunto packages (some are python packages)
setup.d/install-packages.sh

# Install Triage software
setup.d/install-assets.sh

# Install triage services
setup.d/install-wce-triage.sh

