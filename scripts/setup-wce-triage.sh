#!/bin/sh
#
# Install gunpg
sudo apt install -y gnupg
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
User=wce
ExecStart=/usr/bin/sudo -u wce startx /etc/X11/Xsession /usr/local/bin/wce-kiosk.sh --

[Install]
WantedBy=multi-user.target
EOF

sudo install -m 0755 /tmp/wce-kiosk.service /etc/systemd/system/wce-kiosk.service

# Be able to start the tty by user
sudo usermod -a -G tty $USER
# and, be able to start X by user
sudo chmod ug+s /usr/lib/xorg/Xorg

DISTRIBUTOR=`lsb_release -i -s 2> /dev/null || echo Debian`

cat > /tmp/grub.cfg <<EOF
GRUB_DEFAULT=0
GRUB_HIDDEN_TIMEOUT=10
GRUB_TIMEOUT=10
GRUB_DISTRIBUTOR=$DISTRIBUTOR
GRUB_CMDLINE_LINUX_DEFAULT="splash"
GRUB_CMDLINE_LINUX=""
EOF

sudo install /tmp/grub.cfg /etc/default/grub.cfg
sudo update-grub

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

sudo install -m 0755 /tmp/wce-kiosk.service /etc/systemd/system/wce-triage.service

cat > /tmp/wce-triage.sh <<EOF
#!/bin/bash
#
PYTHONPATH=/home/wce/triage python3 /home/wce/triage/start-network.py
PYTHONPATH=/home/wce/triage python3 /home/wce/triage/http/httpserver.py $*
EOF

sudo systemctl daemon-reload

sudo install -m 0555 /tmp/wce-triage.sh /usr/local/bin
