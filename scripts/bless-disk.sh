#!/usr/bin/env bash
#
# bless-disk.sh - re-bless (repair) a broken GRUB/initramfs installation on
# a disk, from a live USB.
#
# What it does: mounts the disk's Linux root partition (and its EFI System
# Partition, if any), chroots in, and regenerates initramfs, grub.cfg, and
# the EFI/BIOS bootloader files from scratch - then, as a safety net,
# double-checks that grub.cfg's root filesystem UUID actually matches the
# partition's real UUID and fixes it if not.
#
# Why that safety net exists: grub-mkconfig determines the root UUID via
# grub-probe -> blkid, and blkid can report a stale/wrong UUID for a
# partition on a disk that has ever carried a different partition layout
# or had a file system UUID changed with tune2fs -U without an
# intervening udev/blkid cache refresh (see wce_triage/ops/tasks.py,
# task_refresh_partitions's docstring, and task_finalize_grub_cfg, which
# hardens the same code path in the automated restore pipeline this
# script exists to fix by hand). This is exactly the failure mode that
# leaves a disk booting into "error: no such device: <uuid>" or hanging
# at GRUB's `normal` command despite the file system itself being fine.
#
# Usage:
#   sudo ./bless-disk.sh /dev/nvme0n1                # whole disk, auto-detect partitions
#   sudo ./bless-disk.sh /dev/sda2                    # explicit root partition, auto-detect EFI
#   sudo ./bless-disk.sh /dev/sda2 /dev/sda1          # explicit root + EFI partition
#   sudo ./bless-disk.sh -y /dev/nvme0n1              # skip the confirmation prompt
#   sudo ./bless-disk.sh -n /dev/nvme0n1              # dry run - detect and print only
#
# Must be run as root, from a live/rescue environment - NOT from the disk
# being blessed (the script refuses to touch whatever disk it booted
# from).

set -euo pipefail

PROGNAME=$(basename "$0")
ASSUME_YES=0
DRY_RUN=0

usage() {
  cat <<EOF
Usage: $PROGNAME [-y] [-n] <disk-or-root-partition> [efi-partition]

  -y   don't ask for confirmation before making changes
  -n   dry run: detect partitions and print what would be done, then exit

Examples:
  sudo $PROGNAME /dev/nvme0n1
  sudo $PROGNAME /dev/sda2 /dev/sda1
EOF
  exit 1
}

log()  { echo "[bless-disk] $*"; }
die()  { echo "[bless-disk] ERROR: $*" >&2; exit 1; }

while getopts ":ynh" opt; do
  case "$opt" in
    y) ASSUME_YES=1 ;;
    n) DRY_RUN=1 ;;
    h) usage ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))

[ "$#" -ge 1 ] || usage
TARGET="$1"
EFI_ARG="${2:-}"

[ "$(id -u)" -eq 0 ] || die "must be run as root (try: sudo $PROGNAME ...)"
[ -e "$TARGET" ] || die "$TARGET does not exist"

for cmd in lsblk findmnt file blkid mount umount chroot grub-install update-grub update-initramfs sed; do
  command -v "$cmd" >/dev/null 2>&1 || die "required command '$cmd' not found - run this from a full live/rescue environment"
done

# ---------------------------------------------------------------------------
# Figure out the whole disk, root partition, and EFI partition.
# ---------------------------------------------------------------------------

lsblk_type() { lsblk -no TYPE "$1" 2>/dev/null | head -1; }
lsblk_fstype() { lsblk -no FSTYPE "$1" 2>/dev/null | head -1; }
parent_disk_of() { lsblk -no PKNAME "$1" 2>/dev/null | head -1; }

TARGET_TYPE=$(lsblk_type "$TARGET")
[ -n "$TARGET_TYPE" ] || die "$TARGET is not a block device lsblk recognizes"

if [ "$TARGET_TYPE" = "disk" ] || [ "$TARGET_TYPE" = "loop" ]; then
  # "loop" covers blessing a disk image file attached via losetup -P,
  # e.g. before it's ever written to real media.
  DISK="$TARGET"
  ROOT_PART=""
elif [ "$TARGET_TYPE" = "part" ]; then
  ROOT_PART="$TARGET"
  pk=$(parent_disk_of "$TARGET")
  [ -n "$pk" ] || die "could not determine the parent disk of $TARGET"
  DISK="/dev/$pk"
else
  die "$TARGET is a '$TARGET_TYPE', expected a disk or partition"
fi

# List this disk's partitions as lsblk "-P" pairs (NAME="..." TYPE="..." ...)
# rather than plain columns - PARTLABEL can legitimately contain spaces
# (parted's own default is the two-word "Linux filesystem"), which would
# silently misalign column-based awk parsing.
list_partitions() {
  lsblk -P -p -o NAME,TYPE,FSTYPE,PARTLABEL,PARTTYPE "$DISK" | awk -F'"' '$4=="part"'
}

# field <lsblk -P line> <KEY> -> that key's value (possibly empty), quotes stripped
field() {
  grep -oP "(?<= |^)$2=\"[^\"]*\"" <<<"$1" | sed -E "s/^$2=\"(.*)\"$/\1/" || true
}

ESP_GUID="c12a7328-f81f-11d2-ba4b-00a0c93ec93b"

if [ -z "$ROOT_PART" ]; then
  # Prefer a partition explicitly named "Linux" (this project's own
  # partitioning convention - see wce_triage/ops/pplan.py), otherwise fall
  # back to the sole ext4 partition on the disk.
  ext4_lines=$(list_partitions | { grep -P 'FSTYPE="ext4"' || true; })
  named_line=$(echo "$ext4_lines" | { grep -P 'PARTLABEL="Linux"' || true; })
  n_ext4=$(echo "$ext4_lines" | grep -c . || true)
  n_named=$(echo "$named_line" | grep -c . || true)

  if [ "$n_named" -eq 1 ]; then
    ROOT_PART=$(field "$named_line" NAME)
  elif [ "$n_ext4" -eq 1 ]; then
    ROOT_PART=$(field "$ext4_lines" NAME)
  else
    log "Found $n_ext4 ext4 partition(s) on $DISK, none uniquely named 'Linux':"
    echo "$ext4_lines" >&2
    die "ambiguous root partition - re-run with it named explicitly: $PROGNAME $DISK <root-partition> [efi-partition]"
  fi
fi

[ "$(lsblk_fstype "$ROOT_PART")" = "ext4" ] || die "$ROOT_PART is not ext4 (found: $(lsblk_fstype "$ROOT_PART"))"

EFI_PART="$EFI_ARG"
if [ -z "$EFI_PART" ]; then
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    [ "$(field "$line" FSTYPE)" = "vfat" ] || continue
    label=$(field "$line" PARTLABEL)
    parttype=$(field "$line" PARTTYPE)
    if [[ "$label" == *EFI* ]] || [ "$(echo "$parttype" | tr '[:upper:]' '[:lower:]')" = "$ESP_GUID" ]; then
      EFI_PART=$(field "$line" NAME)
      break
    fi
  done <<<"$(list_partitions)"
fi
if [ -n "$EFI_PART" ] && [ "$(lsblk_fstype "$EFI_PART")" != "vfat" ]; then
  die "$EFI_PART is not vfat - not a valid EFI System Partition"
fi

# ---------------------------------------------------------------------------
# Safety check: refuse to bless a disk that's currently in use.
#
# A live-USB session's own root is usually an overlayfs over a squashfs,
# not a plain block device mounted at "/" - checking just "/" would miss
# it entirely (confirmed live: this project's own triage USB mounts its
# partitions at /boot/efi and /run/rootfsbase, neither of which is "/").
# So check every currently-mounted source, system-wide, instead.
# ---------------------------------------------------------------------------

running_disks=$(
  findmnt -rno SOURCE | while IFS= read -r src; do
    [ -b "$src" ] || continue
    pk=$(parent_disk_of "$src")
    [ -n "$pk" ] && echo "/dev/$pk"
  done | sort -u
)
if echo "$running_disks" | grep -qx "$DISK"; then
  die "refusing to bless $DISK - it (or a partition on it) is currently mounted on this running system. Boot from a live USB and target a DIFFERENT disk."
fi

log "Disk:            $DISK"
log "Root partition:  $ROOT_PART"
log "EFI partition:   ${EFI_PART:-none found - will install BIOS/legacy GRUB only}"

if [ "$DRY_RUN" -eq 1 ]; then
  log "Dry run requested - not making any changes."
  exit 0
fi

if [ "$ASSUME_YES" -ne 1 ]; then
  read -r -p "[bless-disk] Proceed with re-blessing $ROOT_PART? [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS]) ;;
    *) log "Aborted."; exit 1 ;;
  esac
fi

# ---------------------------------------------------------------------------
# Mount everything under a scratch mountpoint, chroot in, do the work, and
# make sure it's all unmounted again no matter how we exit.
# ---------------------------------------------------------------------------

MNT=$(mktemp -d /tmp/bless-disk.XXXXXX)
MOUNTED=()  # unmount these, in this order, on the way out

cleanup() {
  local rc=$?
  set +e
  for m in "${MOUNTED[@]}"; do
    umount -R "$m" 2>/dev/null || umount -lf "$m" 2>/dev/null || true
  done
  rmdir "$MNT" 2>/dev/null || true
  if [ "$rc" -ne 0 ]; then
    log "FAILED (exit $rc) - see messages above."
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM

mount_and_track() {
  # mount_and_track <mount-args...> <target>
  mount "$@"
  MOUNTED=("${@: -1}" "${MOUNTED[@]}")   # prepend, so cleanup unmounts innermost first
}

log "Mounting $ROOT_PART at $MNT ..."
mount_and_track "$ROOT_PART" "$MNT"

if [ -n "$EFI_PART" ]; then
  mkdir -p "$MNT/boot/efi"
  log "Mounting $EFI_PART at $MNT/boot/efi ..."
  mount_and_track "$EFI_PART" "$MNT/boot/efi"
fi

log "Bind-mounting /dev, /proc, /sys, /dev/pts into the chroot ..."
mount_and_track --bind /dev "$MNT/dev"
mount_and_track --bind /proc "$MNT/proc"
mount_and_track --bind /sys "$MNT/sys"
mount_and_track --bind /dev/pts "$MNT/dev/pts"

log "Regenerating initramfs and grub.cfg inside the chroot ..."
chroot "$MNT" /bin/bash -c '
  set -e
  export GRUB_DISABLE_OS_PROBER=true
  update-initramfs -u -k all
  update-grub
'

if [ -n "$EFI_PART" ]; then
  log "Installing/refreshing the EFI bootloader ..."
  chroot "$MNT" /bin/bash -c '
    set -e
    grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=ubuntu --recheck --force
  '
else
  log "No EFI partition - installing legacy BIOS GRUB to $DISK ..."
  chroot "$MNT" grub-install --target=i386-pc --force "$DISK"
fi

# ---------------------------------------------------------------------------
# Safety net: reconcile grub.cfg's root-fs UUID with the partition's ACTUAL
# UUID. grub-mkconfig (via grub-probe -> blkid) can still get this wrong on
# a disk with leftover signatures from a previous partition layout, or
# right after a tune2fs -U with no udev/blkid cache refresh in between -
# this is the exact failure this script was written to fix.
# ---------------------------------------------------------------------------

log "Verifying grub.cfg's root filesystem UUID against the partition's actual UUID ..."

# `file -sL` reads the ext4 superblock directly - unlike blkid, it can't
# return a stale or "ambivalent" result for a partition with leftover
# signatures from the disk's previous life.
actual_uuid=$(file -sL "$ROOT_PART" | { grep -oP 'UUID="?\K[0-9a-fA-F-]{36}' || true; })
[ -n "$actual_uuid" ] || die "could not determine $ROOT_PART's actual file system UUID via 'file -sL'"

grub_cfg="$MNT/boot/grub/grub.cfg"
[ -f "$grub_cfg" ] || die "$grub_cfg was not created by update-grub"

baked_uuids=$(grep -oP -- '--fs-uuid --set=root \K[0-9a-fA-F-]{36}|root=UUID=\K[0-9a-fA-F-]{36}' "$grub_cfg" | sort -u || true)

if [ -z "$baked_uuids" ]; then
  log "grub.cfg has no 'search --fs-uuid' or 'root=UUID=' references to check - leaving it as generated."
elif [ "$baked_uuids" = "$actual_uuid" ]; then
  log "grub.cfg's UUID ($actual_uuid) already matches the partition. No fix needed."
else
  log "MISMATCH: grub.cfg references $(echo "$baked_uuids" | tr '\n' ' ') but the partition's actual UUID is $actual_uuid - rewriting grub.cfg."
  sed -E -i \
    -e "s/(--fs-uuid --set=root )[0-9a-fA-F-]{36}/\1${actual_uuid}/g" \
    -e "s/(root=UUID=)[0-9a-fA-F-]{36}/\1${actual_uuid}/g" \
    "$grub_cfg"
  log "grub.cfg rewritten to use $actual_uuid throughout."
fi

# Same check for the tiny EFI stub grub.cfg, if grub-install created one
# (see wce_triage/ops/tasks.py task_finalize_efi for the equivalent logic
# in the automated pipeline).
if [ -n "$EFI_PART" ]; then
  for stub in "$MNT/boot/efi/EFI/ubuntu/grub.cfg" "$MNT/boot/efi/boot/grub/grub.cfg"; do
    [ -f "$stub" ] || continue
    stub_uuids=$(grep -oP -- 'fs_uuid \K[0-9a-fA-F-]{36}' "$stub" | sort -u || true)
    if [ -n "$stub_uuids" ] && [ "$stub_uuids" != "$actual_uuid" ]; then
      log "MISMATCH in EFI stub $stub ($stub_uuids != $actual_uuid) - rewriting."
      sed -E -i "s/(fs_uuid )[0-9a-fA-F-]{36}/\1${actual_uuid}/g" "$stub"
    fi
  done
fi

log "Done. $ROOT_PART should now boot cleanly. Unmounting ..."
# cleanup() runs automatically on exit via the trap.
