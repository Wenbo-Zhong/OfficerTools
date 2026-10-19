"""Generate multi-size icons from the UI artwork and embed launcher resources."""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from officertools.catalog import TOOLS
from officertools.icons import render_app_icon, render_icon

ICONS = ROOT / ".toolchain/executable-icons"
SIZES = [(n, n) for n in (16, 24, 32, 48, 64, 128, 256)]


def prepare():
    ICONS.mkdir(parents=True, exist_ok=True)
    render_app_icon().save(ICONS / "OfficerTools.ico", sizes=SIZES)
    for tool in TOOLS:
        render_icon(tool.id, tool.category, 256).save(ICONS / (tool.id + ".ico"), sizes=SIZES)
    print("Generated main icon and", len(TOOLS), "tool icons", flush=True)


def launchers(output, template):
    from PyInstaller.utils.win32.icon import CopyIcons_FromIco
    root = output / "OfficerTools"
    root.mkdir(parents=True, exist_ok=True)
    main = "\u529e\u516c\u5de5\u5177\u7bb1.exe"
    shutil.copy2(output / main, root / main)
    for tool in TOOLS:
        dest = root / "tools" / tool.category / (tool.exe + ".exe")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, dest)
        CopyIcons_FromIco(str(dest), [str(ICONS / (tool.id + ".ico"))])
    print("Created", len(TOOLS), "native launchers with embedded tool icons", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--template", type=Path)
    args = parser.parse_args()
    if args.output:
        if not args.template:
            parser.error("--output requires --template")
        launchers(args.output, args.template)
    else:
        prepare()
