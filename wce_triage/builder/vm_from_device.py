#!/usr/bin/env python3
"""Define and boot a QEMU/KVM virtual machine (via libvirt/virt-install) that
boots directly from an existing raw block device - no ISO, no install step.

Typical use: point this at a disk/USB device wce-triage has already imaged
or installed, to boot and inspect it in a VM without needing to reboot
spare hardware. For building a fresh VM from an Ubuntu ISO instead, see
builder.py.

Requires: virt-install, qemu-kvm, libvirt (apt install virtinst qemu-kvm
libvirt-daemon-system virt-manager).
"""
import argparse
import grp
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REQUIRED_COMMANDS = ["virt-install"]
APT_PACKAGES = ["virtinst", "qemu-kvm", "libvirt-daemon-system", "virt-manager"]


def is_root() -> bool:
    return os.geteuid() == 0


def in_group(name: str) -> bool:
    try:
        group = grp.getgrnam(name)
    except KeyError:
        return False
    return group.gr_gid in os.getgroups()


def confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    reply = input(f"{prompt} [y/N] ").strip().lower()
    return reply in ("y", "yes")


def check_dependencies(assume_yes: bool) -> None:
    missing = [cmd for cmd in REQUIRED_COMMANDS if shutil.which(cmd) is None]
    if missing:
        print(f"Missing required tools: {', '.join(missing)}")
        if not confirm(f"Install with apt ({' '.join(APT_PACKAGES)})?", assume_yes):
            print("Cannot continue without these packages.", file=sys.stderr)
            sys.exit(1)
        cmd = ["apt", "install", "-y", *APT_PACKAGES]
        if not is_root():
            cmd = ["sudo"] + cmd
        result = subprocess.run(cmd)
        if result.returncode != 0:
            sys.exit(result.returncode)
        missing = [cmd for cmd in REQUIRED_COMMANDS if shutil.which(cmd) is None]
        if missing:
            print(f"Still missing after install: {', '.join(missing)}", file=sys.stderr)
            sys.exit(1)
    if not os.path.exists("/dev/kvm"):
        print(
            "Warning: /dev/kvm not found. KVM acceleration is unavailable; "
            "the VM will run (slowly) under pure emulation.",
            file=sys.stderr,
        )


def is_mounted(device: Path) -> bool:
    device_str = str(device.resolve())
    with open("/proc/mounts") as f:
        for line in f:
            mounted_device = line.split()[0]
            # Catches whole-disk-mounted and any partition of it (e.g. /dev/sdb1).
            if mounted_device == device_str or mounted_device.startswith(device_str):
                return True
    return False


def check_device(device: Path, assume_yes: bool) -> None:
    if not device.exists():
        print(f"Device not found: {device}", file=sys.stderr)
        sys.exit(1)
    if not stat.S_ISBLK(device.stat().st_mode):
        print(f"Not a block device: {device}", file=sys.stderr)
        sys.exit(1)
    if is_mounted(device):
        print(f"Warning: {device} (or a partition of it) is currently mounted.", file=sys.stderr)
        if not confirm("Continue anyway?", assume_yes):
            sys.exit(1)
    if not confirm(f"This will boot a VM directly from {device}. Continue?", assume_yes):
        sys.exit(1)


def check_extra_disks(extra_disks: list[Path], allow_shared_disk: bool, assume_yes: bool) -> None:
    for disk in extra_disks:
        if not disk.is_file():
            print(f"Extra disk image not found: {disk}", file=sys.stderr)
            sys.exit(1)
        pass
    if extra_disks and allow_shared_disk:
        print(
            "Warning: --allow-shared-disk bypasses virt-install's check for a disk already "
            "in use by another domain. Never run both domains at the same time - qcow2 does "
            "not support concurrent writers and this will corrupt the disk.",
            file=sys.stderr,
        )
        if not confirm("Continue?", assume_yes):
            sys.exit(1)
        pass


def build_virt_install_cmd(args: argparse.Namespace) -> list[str]:
    cmd = [
        "virt-install",
        "--connect", args.connect,
        "--name", args.name,
        "--memory", str(args.ram),
        "--vcpus", str(args.vcpus),
        "--disk", f"path={args.device},bus={args.bus}",
        "--network", f"network={args.network},model=virtio",
        "--graphics", args.graphics,
        "--video", "virtio",
        # Skips the install process entirely - boots straight off the disk
        # given via --disk, which already has an OS on it.
        "--import",
    ]
    for disk in args.extra_disks:
        # No bus= override here: builder.py doesn't pin one for its qcow2
        # disk either, so virt-install/osinfo picks whatever the detected
        # guest OS normally gets.
        cmd += ["--disk", f"path={disk},format=qcow2"]
        pass
    if args.os_variant:
        cmd += ["--os-variant", args.os_variant]
    else:
        cmd += ["--osinfo", "detect=on,require=false"]
    if args.allow_shared_disk:
        # virt-install refuses by default to attach a disk that's already
        # registered to another domain (e.g. an --extra-disk still owned by
        # the domain that originally created it) - qcow2 has no protection
        # against two domains writing to the same file at once, so this is
        # only safe if the two domains are never run concurrently.
        cmd += ["--check", "path_in_use=off"]
        pass
    return cmd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("device", type=Path, help="raw block device to boot from, e.g. /dev/sdb")
    p.add_argument("--name", default="wce-triage-device", help="libvirt domain name")
    p.add_argument("--ram", type=int, default=4096, help="RAM in MiB")
    p.add_argument("--vcpus", type=int, default=2)
    p.add_argument("--network", default="default", help="libvirt network name")
    p.add_argument("--graphics", default="spice", choices=["spice", "vnc"])
    # sata (AHCI), not virtio: the OS on the device was installed on real
    # hardware (or imaged from it) and its initramfs almost certainly has
    # the AHCI driver built in but not virtio_blk, which is only ever
    # pulled in by installers that already detect they're running in a VM.
    p.add_argument("--bus", default="sata", choices=["sata", "virtio", "scsi", "ide"],
                    help="virtual disk bus the device is attached as (default: sata, for widest guest driver compatibility)")
    p.add_argument("--os-variant", default=None, help="override libosinfo os variant")
    p.add_argument("--connect", default="qemu:///system", help="libvirt connection URI")
    p.add_argument("--extra-disk", type=Path, action="append", default=[], dest="extra_disks",
                    help="additional existing disk image to attach alongside the device "
                         "(e.g. the qcow2 built by builder.py) - repeatable")
    p.add_argument("--allow-shared-disk", action="store_true",
                    help="allow attaching an --extra-disk that's still registered to another "
                         "domain (bypasses virt-install's path_in_use check) - only safe if "
                         "that other domain is never run at the same time as this one")
    p.add_argument("--dry-run", action="store_true", help="print the virt-install command and exit")
    p.add_argument("-y", "--yes", action="store_true",
                    help="don't prompt before using sudo or booting from the device")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    check_dependencies(args.yes)
    check_device(args.device, args.yes)
    check_extra_disks(args.extra_disks, args.allow_shared_disk, args.yes)
    cmd = build_virt_install_cmd(args)

    needs_sudo = (
        not is_root()
        and args.connect == "qemu:///system"
        and not in_group("libvirt")
    )
    if needs_sudo:
        print("Not a member of the 'libvirt' group; running virt-install via sudo.")
        cmd = ["sudo"] + cmd

    print("Running:", " ".join(cmd))
    if args.dry_run:
        return

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
