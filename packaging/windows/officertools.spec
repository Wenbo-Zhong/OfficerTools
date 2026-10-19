# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
root = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

a = Analysis(
    [os.path.join(root, "officertools", "__main__.py")],
    pathex=[root],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("officertools") + collect_submodules("pypdf") + ["PIL.ImageGrab", "qrcode", "barcode"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "matplotlib", "pandas", "scipy", "cryptography", "psutil", "setuptools", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
# Drop Anaconda/numpy libraries if a hook still picked them up. They are not used,
# and their extra DLLs are what makes LoadLibrary fail on a clean machine.
a.binaries = [item for item in a.binaries if "numpy" not in item[0].lower() and "mkl" not in item[0].lower()]
a.datas = [item for item in a.datas if "numpy" not in item[0].lower() and "mkl" not in item[0].lower()]
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="办公工具箱",
    icon=os.path.join(root, ".toolchain", "executable-icons", "OfficerTools.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    manifest=os.path.join(SPECPATH, "app.manifest"),
)
