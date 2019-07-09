#
#
#
if [ "x${TRIAGEUSER}" = "x" ] ; then
    TRIAGEUSER=triage
fi

sudo mkdir -p /usr/local/share/wce
sudo mkdir -p /usr/local/share/wce/wce-triage-ui
sudo chown $TRIAGEUSER:$TRIAGEUSER /usr/local/share/wce/wce-triage-ui
sudo mkdir -p /usr/local/share/wce/triage/bin
sudo mkdir -p /usr/local/share/wce/triage/assets
sudo mkdir -p /usr/local/share/wce/ubuntu-packages
sudo chown $TRIAGEUSER:$TRIAGEUSER /usr/local/share/wce/ubuntu-packages

cd /usr/local/share/wce/ubuntu-packages
#
apt download grub-efi-amd64
#
nvidia_driver=$(apt search xserver-xorg-video-nvidia 2> /dev/null | awk -F / '/xserver-xorg-video-nvidia/ { print $1 }')
apt download $nvidia_driver

# Create default update script.
# If download succeeds, the updated update-wce-triage would run.
# At minimum, the UI and wce_triage package needs to be updated.
# When the UI distribution method changes, this might change.
cd /usr/local/share/wce/triage/bin
cat > /tmp/update-wce-triage <<EOF
#!/bin/sh
sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage
cd /usr/local/share/wce/wce-triage-ui
wget --user=triage --password=triage -q -O - http://release.cleanwinner.com/wce/wce-triage-ui.tgz | tar xzf -
EOF
sudo install -m 555 /tmp/update-wce-triage /usr/local/share/wce/triage/bin

wget --user=triage --password=thepasswordiswcetriage -q -O - http://release.cleanwinner.com/wce/update-wce-triage && chmod +x update-wce-triage
#
sh update-wce-triage
