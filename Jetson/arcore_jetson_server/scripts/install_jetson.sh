#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sudo apt update
sudo apt install -y python3-venv python3-pip python3-dev python3-smbus i2c-tools libgpiod2

python3 -m venv --system-site-packages "$PROJECT_DIR/.venv"
source "$PROJECT_DIR/.venv/bin/activate"
python -m pip install --upgrade pip wheel
python -m pip install -r "$PROJECT_DIR/requirements.txt"

sudo groupadd -f gpio
sudo usermod -aG gpio "$USER"
sudo usermod -aG i2c "$USER"

printf '\nInstallation complete. Log out and back in once so group changes apply.\n'
printf 'Then run: %s/scripts/run_jetson.sh\n' "$PROJECT_DIR"
