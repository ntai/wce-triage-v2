# WCE Triage

## About World Computer Exchange
World Computer Exchange (WCE) is a volunteer organization, located in Hull, Massachussets, USA.
The primary mission of WCE is to refurbish and reuse computers in developing countries.
See https://www.worldcomputerexchange.org for more details.

## What is WCE Triage?
When a donated computer arrives, the volunteers first physically clean and assess the computer.
We call this process triaging.
For hardware, volunteers replace or install components as neeeded based on the triage.
In order to streamline and have consistent decisions about the state of computer, we use software to gather information.

Since WCE ships the computers with Ubuntu as OS, it makes sense to run Ubuntu to triage.

This package is designed around running a minimal Ubuntu/Linux, and gather computer states, and displays the triage information.

In order to run the triage, you boot the computer using a USB stick with the triage software on it. During triage, the network/sound is tested as well.

## What's in the triage?

- It boots a minimalistic Linux based on Ubuntu's mini.iso (reducing the size footprint is essential.)
- When it boots, it starts two services "wce-triage" and "wce-kiosk".
- wce-triage is the backend of triage software. It gathers up the machine's information and provides it through HTTP.
- wce-kiosk is the frontend. It's Google Chrome in kiosk mode that talks to the backend and display.

### wce-triage overview
The core of WCE triage is written in Python3. The reason is that, the mini.iso of Ubuntu 18.04LTS includes Python3 already so to not increase the footprint, Python3 is a natural choice. The source code is available at https://github.com/ntai/wce-triage-v2. (This readme is part of it.)
The details are in the latter part of this document.

### wce-kiosk overview
The frontend UI uses React.js, and the source is available at https://github.com/ntai/wce-triage-ui. For the details, please see the project document.
it's developed on Mac by me at the moment, and quite crude. The release build does not require anything extra from internet, and HTTP server in wce-triage handles the requests.

# WCE Triage details
The package provides following features:

 - Triage information gathering and decision making
 - Initialize/partition triage USB stick
 - Initialize/partition disk for WCE's computers
 - Create disk image from partition (aka image disk)
 - Load disk image to partition (aka load/restore disk)
 - Make usb stick/disk bootable
 - HTTP server for WCE Kiosk web browser

## Triage information gathering and decision making

Information gathering of individual component is in each python module in wce_triage/components, except computer/Computer.
Currently, following components are implemented. 
 - cpu.py
 - disk.py
 - memory.py
 - network.py
 - optical_drive.py
 - pci.py
 - sensor.py
 - sound.py
 - video.py

The module name says pretty much what it is. Disk and network are somewhat special as the rest of wce-triage uses the instances of disk and network during not just triaging but imaging/restoring partclone image as well as starting network during triage.

Computer module collects the components' information and makes the triage decision. The criteria of triage is decided by WCE.

## Creating Bootable Installer

### Step 1: Acquire Ubuntu 18.04LTS mini.iso installer
  Making a bootable USB stick from mini.iso is tricky.
  'Create Installer' of Ubuntu does not work for mini.iso.

  For Mac:
    Use balenaEtcher. This macOS app works and probably the simplest.

  For Linux:
    Most likely, "dd" works. Find out the USB stick device and
    dd if=mini.iso of=/dev/<USB_STICK_DEVICE> bs=1M

### Step 2: Install mini.iso to a disk
  Disk can be an external disk, USB stick, etc.
  I recommend using a normal disk (or SSD) to make it faster rather than USB stick.
  Boot from mini.iso bootable and install minimal.
  Machine name is "wcetriage".
  User name/password is "triage/triage".

### Step 3: Bootstrap
  Once installation is done, boot into the installed system.
  One way or the other, you need to get network going. mini.iso is barebone (on purpose.)

  Here is what you can do:
  * if you have an ethernet, use it. First, find out the ethernet device name.

    $ ip  addr

    Usually, "lo" is the loopback device and first. 2nd and on is the network device.
    2: <YOUR-DEVICE-HERE>: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500...

  * create netplan file
    $ sudo mkdir /run/netplan
    Using text editor, create a netplan file as follow. Indentation is critial to netplan so this shoud look exactly as follow:
    /run/netplan/bootstrap.yaml

----- THIS LINE NOT INCLUDED IN run/netplan/bootstrap.yaml ------
network: 
  version: 2
  renderer: networkd
  ethernets:
    <YOUR-DEVICE-HERE>:
      dhcp4: yes
      optional: yes
----- THIS LINE NOT INCLUDED IN run/netplan/bootstrap.yaml ------

   * start network
     $ sudo netplan generate
     $ sudo netplan apply

### Step 4: Download wce_triage software
  $ sudo -H apt install -y python3-pip
  $ sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage

  At this point, if you want to switch over to use WIFI instead of ethernet, you can do so by

  $ sudo -H python3 -m wce_traige.bin.start_network

  This module scans the network devices and runs netplan. If you want to use WIFI, set up a guest network as follow:
  SSID: wcetriage
  Wifi password: thepasswordiswcetriage
  
  You can use your existing network.
  $ export TRIAGE_SSID=<YOUR-SSID>
  $ export TRIAGE_PASSWORD=<YOUR-WIFI-PASSWORD>
  $ sudo -H python3 -m wce_traige.bin.start_network

  "wcetriage" - is used for testing WIFI device during WCE's triage.
  In other word, if you have a wifi router with wcetriage/thepasswordiswcetriage, running triage software automatically connects to the wifi router thus it tests the WIFI device.


### Step 5: Install the rest of WCE triage assets and set up the installer.

  $ python3 -m wce_triage.setup.setup_triage_system

  You should run this from terminal. It probably asks you some questions. Answer appropriately.
  For grub installation, install to the disk device you booted.
