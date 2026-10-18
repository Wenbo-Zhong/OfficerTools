#!/bin/sh
# One launcher binary. Open a tool with: ./officertools <tool-id>
set -eu
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
python3 -m PyInstaller --noconfirm --clean --name officertools \
  --collect-submodules officertools \
  --collect-submodules pypdf \
  officertools/__main__.py
echo "Output: dist/officertools"
