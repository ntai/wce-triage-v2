# Building a WCE triage OS with Ubuntu 18.04 and Chrome

We’re going to be running a very light stack of X, Openbox and the Google Chrome web browser.

The whole thing takes less than 3GB of disk space and can run on 512MB of RAM.


## Step 1: Installing Ubuntu 18.04 mini

Follow the installation instructions. Do not enable automatic update. Install OpenSSH server or else make life miserable typeing in small console.
Hostname: wcetriage
For username/password - triage/triage

Do not install Network Manager.

## Step 2: Install all the things
There are two options - one is to install Google Chrome, and other is to install Chromium. I followed the instruction of installing minimum Chrome but seems pointless at this point. Just install chromium-browser and be done with it. So that would be "apt install --no-install-recommends chromium-browser". 

I will leave how to install Chrome anyway here, rather for histric reason.

    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    echo 'deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main' | sudo tee /etc/apt/sources.list.d/google-chrome.list

Using add-apt-repository using google's source list result in error as it exports both i386 and amd64 but 18.04 doesn't support i386 and complains.

    sudo apt update
    sudo apt install --no-install-recommends xorg openbox google-chrome-stable pulseaudio
    sudo usermod -a -G audio $USER

## Step 3: Install wce_triage python package

    $ sudo -H apt install --no-install-recommends -y python3-pip
    $ sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage


    $ sudo -H python3 -m wce_triage.setup.setup_triage_system

This should take care of setting up the triage system. If not, following historic things to test out the problem.


## Loading the browser on boot
### /usr/local/bin/wce-kiosk.sh

    #!/bin/bash
    xset -dpms
    xset s off
    openbox-session &
    start-pulseaudio-x11

    while true; do
      rm -rf ~/.{config,cache}/google-chrome/
      google-chrome --kiosk --no-first-run  'http://localhost'
    done
Set the executable to the wce-kiosk.sh
    sudo chmod +x /usr/local/bin/wce-kiosk.sh

### /etc/systemd/system/wce-kiosk.service and this time fill it with:

**NOTE**- if you change the wce-kiosk.service run

    systemctl daemon-reload
---

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

### Allow X server to start by wce

    sudo usermod -a -G tty wce
     
and selecting “Anybody”.

    sudo chmod ug+s /usr/lib/xorg/Xorg 

Apparently this is a bad thing to do from security point of view, 

### Test
Run 
    sudo start wce-kiosk

### /etc/default/grub.cfg

    GRUB_DEFAULT=0
    GRUB_HIDDEN_TIMEOUT=10
    # GRUB_HIDDEN_TIMEOUT_QUIET=true
    GRUB_TIMEOUT=10
    GRUB_DISTRIBUTOR=`lsb_release -i -s 2> /dev/null || echo Debian`
    GRUB_CMDLINE_LINUX_DEFAULT="splash"
    GRUB_CMDLINE_LINUX=""

Save and exit that and run 
    sudo update-grub


## Update
While development, xorg x-server came out with 2 flavors. HWE (Hardware Enabled) and normal (non-HWE). I'm not quite sure of which is better. I assume HWE is faster but might be more machine dependant. OTOH, running X11 with framebuffer based driver should be avoided but probably more compatible. For the scheme of triage, this might be more preferable as it's simplest form of pushing pixel to screen. We have to keep an eye on updates of Xorg.
