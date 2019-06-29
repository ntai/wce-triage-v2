#
#
#
sudo mkdir -p /usr/local/share/wce
sudo chown triage:triage /usr/local/share/wce
mkdir -p /usr/local/share/wce/wce-triage-ui
mkdir -p /usr/local/share/wce/triage/bin
mkdir -p /usr/local/share/wce/triage/assets
mkdir -p /usr/local/share/wce/ubuntu-packages

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
cat > update-wce-triage <<EOF
#!/bin/sh
sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage
cd /usr/local/share/wce/wce-triage-ui
wget --user=triage --password=triage -q -O - http://release.cleanwinner.com/wce/wce-triage-ui.tgz | tar xzf -
EOF
chmod +x update-wce-triage

wget --user=triage --password=triage -q -O - http://release.cleanwinner.com/wce/update-wce-triage && chmod +x update-wce-triage
#
sh update-wce-triage
