#!/usr/bin/env python3
"""Create a QEMU/KVM virtual machine (via libvirt/virt-install) for Ubuntu Server.

Downloads the official server ISO, verifies its SHA256 checksum, then hands
off to `virt-install` to define and boot the VM. The VM is a normal libvirt
domain, so it shows up in virt-manager immediately for GUI console access.

Requires: virt-install, qemu-kvm, libvirt (apt install virtinst qemu-kvm
libvirt-daemon-system virt-manager).
"""
import argparse
import grp
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

UBUNTU_RELEASES_BASE = "https://releases.ubuntu.com"
# The default libvirt storage pool - qemu:///system's libvirt-qemu user can
# always read from here, unlike a path under $HOME (which is typically not
# world-traversable). Root-owned (mode 711), so writing into it needs sudo -
# see download()/ensure_iso() below.
DEFAULT_ISO_DIR = Path("/var/lib/libvirt/images")
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


def run_as_root(cmd: list[str]) -> subprocess.CompletedProcess:
    if not is_root():
        cmd = ["sudo"] + cmd
    print("Running:", " ".join(cmd))
    return subprocess.run(cmd)


def check_dependencies(assume_yes: bool) -> None:
    missing = [cmd for cmd in REQUIRED_COMMANDS if shutil.which(cmd) is None]
    if missing:
        print(f"Missing required tools: {', '.join(missing)}")
        if not confirm(f"Install with apt ({' '.join(APT_PACKAGES)})?", assume_yes):
            print("Cannot continue without these packages.", file=sys.stderr)
            sys.exit(1)
        result = run_as_root(["apt", "install", "-y", *APT_PACKAGES])
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


def fetch_iso_info(release: str, arch: str) -> tuple[str, str]:
    sums_url = f"{UBUNTU_RELEASES_BASE}/{release}/SHA256SUMS"
    with urllib.request.urlopen(sums_url) as resp:
        sums_text = resp.read().decode()

    pattern = re.compile(rf"^([0-9a-f]{{64}})\s+\*?(.*live-server-{arch}\.iso)$", re.MULTILINE)
    match = pattern.search(sums_text)
    if not match:
        raise RuntimeError(
            f"Could not find a live-server-{arch}.iso entry in {sums_url}"
        )
    sha256, filename = match.group(1), match.group(2)
    return filename, sha256


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dest: Path) -> None:
    print(f"Downloading {url} -> {dest}")
    needs_root = not is_root() and not os.access(dest.parent, os.W_OK)
    # Can't write straight into dest (e.g. the default /var/lib/libvirt/images,
    # which is root-owned) - fetch to a scratch dir the current user can
    # write, then hand the finished, checksum-verifiable file off to root.
    fetch_dest = Path(tempfile.mkdtemp(prefix="wce-builder-")) / dest.name if needs_root else dest
    try:
        if shutil.which("curl"):
            subprocess.run(["curl", "-L", "-C", "-", "-o", str(fetch_dest), url], check=True)
        else:
            urllib.request.urlretrieve(url, fetch_dest)
        if needs_root:
            result = run_as_root(["install", "-m", "644", str(fetch_dest), str(dest)])
            if result.returncode != 0:
                sys.exit(result.returncode)
            pass
        pass
    finally:
        if needs_root:
            shutil.rmtree(fetch_dest.parent, ignore_errors=True)
            pass
        pass


def ensure_iso(args: argparse.Namespace) -> Path:
    if args.iso:
        iso_path = Path(args.iso).expanduser()
        if not iso_path.is_file():
            print(f"ISO not found: {iso_path}", file=sys.stderr)
            sys.exit(1)
        return iso_path

    try:
        args.iso_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        run_as_root(["mkdir", "-p", str(args.iso_dir)])
        pass
    filename, expected_sha256 = fetch_iso_info(args.release, args.arch)
    iso_path = args.iso_dir / filename
    iso_url = f"{UBUNTU_RELEASES_BASE}/{args.release}/{filename}"

    if iso_path.is_file() and not args.force_download:
        print(f"Found cached ISO at {iso_path}, verifying checksum...")
        if sha256_of(iso_path) == expected_sha256:
            print("Checksum OK, reusing cached ISO.")
            return iso_path
        print("Checksum mismatch, redownloading.")

    download(iso_url, iso_path)

    print("Verifying checksum...")
    actual_sha256 = sha256_of(iso_path)
    if actual_sha256 != expected_sha256:
        try:
            iso_path.unlink(missing_ok=True)
        except PermissionError:
            run_as_root(["rm", "-f", str(iso_path)])
            pass
        print(
            f"Checksum mismatch for {filename}: "
            f"expected {expected_sha256}, got {actual_sha256}",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Checksum OK.")
    return iso_path


def build_virt_install_cmd(args: argparse.Namespace, iso_path: Path) -> list[str]:
    cmd = [
        "virt-install",
        "--connect", args.connect,
        "--name", args.name,
        "--memory", str(args.ram),
        "--vcpus", str(args.vcpus),
        "--disk", f"size={args.disk_size},format=qcow2",
        "--cdrom", str(iso_path),
        "--network", f"network={args.network},model=virtio",
        "--graphics", args.graphics,
        "--video", "virtio",
    ]
    if args.os_variant:
        cmd += ["--os-variant", args.os_variant]
    else:
        cmd += ["--osinfo", "detect=on,require=false"]
    return cmd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", default="ubuntu-server", help="libvirt domain name")
    p.add_argument("--release", default="26.04", help="Ubuntu release, e.g. 26.04")
    p.add_argument("--arch", default="amd64")
    p.add_argument("--ram", type=int, default=4096, help="RAM in MiB")
    p.add_argument("--vcpus", type=int, default=2)
    p.add_argument("--disk-size", type=int, default=40, help="Disk size in GiB")
    p.add_argument("--network", default="default", help="libvirt network name")
    p.add_argument("--graphics", default="spice", choices=["spice", "vnc"])
    p.add_argument("--os-variant", default=None, help="override libosinfo os variant")
    p.add_argument("--connect", default="qemu:///system", help="libvirt connection URI")
    p.add_argument("--iso", default=None, help="use this local ISO instead of downloading")
    p.add_argument("--iso-dir", type=Path, default=DEFAULT_ISO_DIR)
    p.add_argument("--force-download", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="print the virt-install command and exit")
    p.add_argument("-y", "--yes", action="store_true", help="don't prompt before using sudo")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    check_dependencies(args.yes)
    iso_path = ensure_iso(args)
    cmd = build_virt_install_cmd(args, iso_path)

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
