#!/bin/bash
# Fresh-install setup for wce-triage-v2 (Xubuntu LTS 26.04+): installs git if
# missing, checks out the repo into /usr/local/share/wce/triage, builds its
# venv, then hands off to install_wce_triage.py to wire up the systemd
# service. Re-runnable: an existing checkout is updated with `git pull`
# instead of re-cloned.
set -euo pipefail

REPO_URL="https://github.com/ntai/wce-triage-v2"
TRIAGE_DIR="/usr/local/share/wce/triage"
REPO_DIR="$TRIAGE_DIR/wce-triage-v2"

if ! command -v git >/dev/null 2>&1; then
  sudo -H apt update
  sudo -H apt install -y git
fi

sudo -H mkdir -p "$TRIAGE_DIR"

if [ -d "$REPO_DIR/.git" ]; then
  sudo -H git -C "$REPO_DIR" pull
else
  sudo -H git clone "$REPO_URL" "$REPO_DIR"
fi

# install_wce_triage.py's generated /usr/local/bin/wce-triage.sh expects a
# venv at $REPO_DIR/venv with uvicorn installed - build that here.
sudo -H apt install -y python3-venv
sudo -H python3 -m venv "$REPO_DIR/venv"
sudo -H "$REPO_DIR/venv/bin/pip" install --upgrade pip
# Editable install: a later `git pull` + service restart alone picks up new
# code, no reinstall needed.
sudo -H "$REPO_DIR/venv/bin/pip" install -e "$REPO_DIR"

"$REPO_DIR/venv/bin/python3" -m wce_triage.setup.install_wce_triage
