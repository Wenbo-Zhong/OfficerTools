#!/bin/sh
# Run this on a Mac. It produces one OfficerTools.app that contains every tool.
set -eu
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt 'cmake>=3.24,<4'
python3 packaging/macos/prepare_llama.py
python3 -m PyInstaller --noconfirm --clean --windowed --name OfficerTools \
  --osx-bundle-identifier local.officertools.app \
  --add-data ".toolchain/release-macos/models:models" \
  --add-data ".toolchain/release-macos/vendor:vendor" \
  --add-data ".toolchain/release-macos/licenses:licenses" \
  --add-data ".toolchain/release-macos/sources:sources" \
  --add-binary ".toolchain/release-macos/tesseract-bin/tesseract:vendor/tesseract/bin" \
  --collect-submodules officertools \
  --collect-submodules pypdf \
  officertools/__main__.py
echo "Output: dist/OfficerTools.app"
