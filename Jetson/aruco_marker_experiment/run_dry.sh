#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 navigation.py --config config.json --route route.json
