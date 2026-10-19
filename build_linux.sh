#!/bin/sh
# Build a single-file Ubuntu GUI application.
set -eu
cd "$(dirname "$0")"
CONDA="$(command -v conda || true)"
if [ ! -x .toolchain/linux-runtime/bin/ffmpeg ]; then
  if [ -z "$CONDA" ]; then
    echo "Conda is required to prepare the pinned Ubuntu runtime components." >&2
    exit 1
  fi
  "$CONDA" env create --yes --prefix .toolchain/linux-runtime --file packaging/linux/environment.yml
fi
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ] && [ -x .toolchain/linux-build/bin/python ]; then
  PYTHON=.toolchain/linux-build/bin/python
fi
if [ -z "$PYTHON" ] && [ -n "$CONDA" ]; then
  "$CONDA" create --yes --prefix .toolchain/linux-build -c conda-forge python=3.12 pip tk
  PYTHON=.toolchain/linux-build/bin/python
fi
if [ -z "$PYTHON" ]; then PYTHON=python3; fi
"$PYTHON" -m pip install -r requirements.txt
PATH="$(pwd)/.toolchain/linux-runtime/bin:$PATH" "$PYTHON" packaging/linux/prepare_payload.py
BUILD_LIB="$(cd "$(dirname "$PYTHON")/../lib" && pwd)"
if [ -f "$BUILD_LIB/libtk8.6.so" ] && [ -f "$BUILD_LIB/libtcl8.6.so" ]; then
  TK_BACKUP="$(pwd)/.toolchain/linux-tk-backup"
  mkdir -p "$TK_BACKUP"
  cp "$BUILD_LIB/libtk8.6.so" "$TK_BACKUP/libtk8.6.so"
  cp "$BUILD_LIB/libtcl8.6.so" "$TK_BACKUP/libtcl8.6.so"
  restore_conda_tk() {
    cp "$TK_BACKUP/libtk8.6.so" "$BUILD_LIB/libtk8.6.so"
    cp "$TK_BACKUP/libtcl8.6.so" "$BUILD_LIB/libtcl8.6.so"
  }
  trap restore_conda_tk EXIT HUP INT TERM
  cp .toolchain/linux-payload/vendor/system-tk/lib/libtk8.6.so "$BUILD_LIB/libtk8.6.so"
  cp .toolchain/linux-payload/vendor/system-tk/lib/libtcl8.6.so "$BUILD_LIB/libtcl8.6.so"
  export TCL_LIBRARY="$(pwd)/.toolchain/linux-payload/vendor/system-tk/tcl8.6"
  export TK_LIBRARY="$(pwd)/.toolchain/linux-payload/vendor/system-tk/tk8.6"
fi
set --
for binary in .toolchain/linux-binaries/vendor/Library/bin/* .toolchain/linux-binaries/vendor/ghostscript/bin/* .toolchain/linux-binaries/vendor/tesseract/bin/* .toolchain/linux-binaries/vendor/llama.cpp/cpu/*; do
  if [ -f "$binary" ]; then
    relative=${binary#.toolchain/linux-binaries/}
    set -- "$@" --add-binary "$binary:$(dirname "$relative")"
  fi
done
"$PYTHON" -m PyInstaller --noconfirm --clean --onefile --windowed \
  --name OfficerTools \
  --collect-submodules officertools \
  --collect-submodules pypdf \
  --hidden-import PIL._tkinter_finder \
  "$@" \
  --add-data ".toolchain/linux-payload:." \
  officertools/__main__.py
chmod +x dist/OfficerTools
if [ -n "${TK_BACKUP:-}" ]; then
  restore_conda_tk
  trap - EXIT HUP INT TERM
fi
echo "Output: dist/OfficerTools"
