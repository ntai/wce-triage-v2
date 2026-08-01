#!/bin/bash
# Disk-space minimization for the Xubuntu 26.04 golden image, run once
# setup-triage.sh has finished and before the image is captured (partclone)
# for cloning onto donated machines. Strips docs, man pages, non-English
# locales, apt/log/cache cruft, then zero-fills free space so the captured
# image compresses tighter with pigz. Re-runnable.
#
# Deliberately leaves build-essential, gcc, dkms and linux-headers-* alone:
# r8125-dkms/r8168-dkms/broadcom-sta-dkms/rtl8812au-dkms (see
# wce_triage/setup/install_packages.py) need them to rebuild kernel modules
# whenever a donated machine's kernel is updated - stripping them would
# quietly break wifi/ethernet on the next kernel upgrade in the field.
set -euo pipefail

echo "=== disk usage before ==="
df -h /

echo "=== apt: removing unused packages and caches ==="
sudo -H apt-get autoremove --purge -y
sudo -H apt-get clean
sudo -H rm -rf /var/lib/apt/lists/*

echo "=== blocking future doc/man/locale reinstalls ==="
# A later `apt install` (during triage itself, or a stray upgrade) would
# otherwise drop docs/man pages/locale files right back in.
sudo -H tee /etc/dpkg/dpkg.cfg.d/01_nodoc >/dev/null <<'EOF'
path-exclude=/usr/share/doc/*
path-exclude=/usr/share/man/*
path-exclude=/usr/share/groff/*
path-exclude=/usr/share/info/*
path-exclude=/usr/share/lintian/*
path-exclude=/usr/share/linda/*
# dpkg-provided copyright files are tiny and sometimes needed for license compliance
path-include=/usr/share/doc/*/copyright
EOF
sudo -H tee /etc/dpkg/dpkg.cfg.d/01_nolocale >/dev/null <<'EOF'
path-exclude=/usr/share/locale/*
path-include=/usr/share/locale/en*/*
path-include=/usr/share/locale/locale.alias
EOF

echo "=== removing existing docs, man pages, info pages ==="
sudo -H rm -rf /usr/share/doc/* /usr/share/man/* /usr/share/groff/* /usr/share/info/*

echo "=== removing non-English locale data ==="
sudo -H find /usr/share/locale -mindepth 1 -maxdepth 1 -type d ! -name 'en*' -exec rm -rf {} +
dpkg -l | awk '/^ii  language-pack-/{print $2}' | grep -v -E '^language-pack-en' \
  | xargs -r sudo -H apt-get purge -y

echo "=== vacuuming logs and crash reports ==="
sudo -H journalctl --vacuum-time=1d || true
sudo -H find /var/log -type f \( -name '*.gz' -o -name '*.[0-9]' -o -name '*.old' \) -delete
sudo -H find /var/log -type f -name '*.log' -exec truncate -s 0 {} +
sudo -H rm -rf /var/crash/*

echo "=== clearing per-user caches and trash ==="
for home in /root /home/*; do
  [ -d "$home" ] || continue
  sudo -H rm -rf "$home/.cache" "$home/.local/share/Trash"
done

echo "=== removing disabled snap revisions ==="
if command -v snap >/dev/null 2>&1; then
  snap list --all | awk '/disabled/{print $1, $3}' | while read -r name rev; do
    sudo -H snap remove "$name" --revision="$rev" || true
  done
fi

echo "=== zero-filling free space for tighter image compression ==="
# partclone/pigz (see wce_triage/setup/install_packages.py) compress the
# captured image far better when free blocks are zeroed instead of left as
# filesystem noise from deleted files.
sudo -H dd if=/dev/zero of=/ZEROFILL bs=1M status=progress || true
sync
sudo -H rm -f /ZEROFILL

echo "=== disk usage after ==="
df -h /
