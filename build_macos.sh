#!/bin/sh
# Run this on a Mac. It produces one OfficerTools.app that contains every tool.
set -eu
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
python3 -m PyInstaller --noconfirm --clean --windowed --name OfficerTools \
  --osx-bundle-identifier local.officertools.app \
  --collect-submodules officertools \
  --collect-submodules pypdf \
  officertools/__main__.py
echo "Output: dist/OfficerTools.app"
