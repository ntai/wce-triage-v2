#!/bin/sh

export GRUB_DISABLE_OS_PROBER=true

#
# Install Ubunto packages (some are python packages)
#
for pkg in gnupg dmidecode partclone mbr efibootmgr grub2-common grub-pc pigz vbetool gfxboot alsa-utils pulseaudio pulseaudio-utils mpg123 python3-aiohttp python3-aiohttp-cors; do
    sudo apt install -y $pkg
done

# install python packages
for pkg in python-socketio; do
    sudo pip3 install -y $pkg
done


#
# Add Google signing key
#
wget -qO- https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -

# Using add-apt-repository using google's source list result in error as it exports both i386 and amd64 but 18.04 doesn't support i386 and complains.
#
echo 'deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main' | sudo tee /etc/apt/sources.list.d/google-chrome.list

#
sudo apt update
#
# Install Google Chrome
#
sudo apt install -y --no-install-recommends xorg openbox google-chrome-stable pulseaudio
#
sudo usermod -a -G audio $USER
#
cat > /tmp/wce-kiosk.sh <<EOF
#!/bin/bash
xset -dpms
xset s off
openbox-session &
start-pulseaudio-x11

while true; do
  rm -rf ~/.{config,cache}/google-chrome/
  google-chrome --kiosk --no-first-run  'http://localhost:8312'
done
EOF

sudo install -m 0555 /tmp/wce-kiosk.sh /usr/local/bin

#
#
#
cat > /tmp/wce-kiosk.service <<EOF
[Unit]
Description=WCE Kiosk Web Browser
After=dbus.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User=triage
ExecStart=/usr/bin/sudo -u triage startx /etc/X11/Xsession /usr/local/bin/wce-kiosk.sh --

[Install]
WantedBy=multi-user.target
EOF

sudo install -m 0755 /tmp/wce-kiosk.service /etc/systemd/system/wce-kiosk.service

# Be able to start the tty by user
sudo usermod -a -G tty $USER
# and, be able to start X by user
sudo chmod ug+s /usr/lib/xorg/Xorg

#
# Now the triage http server service that produces the triage output
#
cat > /tmp/wce-triage.service <<EOF
[Unit]
Description=WCE Triage service
After=dbus.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User=root
ExecStart=/usr/local/bin/wce-triage.sh

[Install]
WantedBy=multi-user.target
EOF

sudo install -m 0755 /tmp/wce-triage.service /etc/systemd/system/wce-triage.service

cat > /tmp/wce-triage.sh <<EOF
#!/bin/bash
#
python3 -m wce_triage.bin.start_network
cd /usr/local/share/wce/wce-triage-ui
python3 -m wce_triage.http.httpserver $*
EOF

sudo install -m 0555 /tmp/wce-triage.sh /usr/local/bin

sudo systemctl daemon-reload
sudo systemctl enable wce-kiosk.service
sudo systemctl enable wce-triage.service

cat > /tmp/grub.cfg <<EOF
GRUB_DEFAULT=0
GRUB_TIMEOUT=10
GRUB_DISTRIBUTOR=Ubuntu
GRUB_CMDLINE_LINUX_DEFAULT=""
GRUB_CMDLINE_LINUX=""
EOF

sudo install /tmp/grub.cfg /etc/default/grub
sudo update-grub
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

