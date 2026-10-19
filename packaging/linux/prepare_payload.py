"""Assemble Linux-native offline runtimes and models for the one-file build."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PREFIX = ROOT / ".toolchain/linux-runtime"
STAGE = ROOT / ".toolchain/linux-payload"
CACHE = ROOT / ".toolchain/vendor"
EXECUTABLES = ROOT / ".toolchain/linux-binaries"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download(url: str, target: Path, expected: str | None = None) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and (not expected or sha256(target) == expected):
        return target
    temp = target.with_suffix(target.suffix + ".part")
    subprocess.run(["curl", "--silent", "--show-error", "--fail", "--location", "--retry", "8",
                    "--retry-all-errors", "--continue-at", "-", "--output", str(temp), url], check=True)
    if expected and sha256(temp) != expected:
        raise RuntimeError("SHA256 mismatch: " + url)
    temp.replace(target)
    return target


def copy_runtime():
    if not (PREFIX / "conda-meta").is_dir():
        raise RuntimeError("Ubuntu runtime environment is missing: " + str(PREFIX))
    if STAGE.exists():
        shutil.rmtree(STAGE)
    root = STAGE
    bins = root / "vendor/Library/bin"
    bins.mkdir(parents=True)
    for name in ("ffmpeg", "ffprobe", "pdftoppm", "pdftocairo", "pdfinfo"):
        source = PREFIX / "bin" / name
        if source.is_file():
            shutil.copy2(source, bins / name)
    gs = PREFIX / "bin/gs"
    if not gs.is_file():
        raise RuntimeError("Ghostscript was not installed in the Ubuntu environment")
    ghost = root / "vendor/ghostscript/bin"
    ghost.mkdir(parents=True)
    shutil.copy2(gs, ghost / "gs")
    tess_bin = root / "vendor/tesseract/bin"
    tess_bin.mkdir(parents=True)
    tesseract = PREFIX / "bin/tesseract"
    if not tesseract.is_file():
        raise RuntimeError("Tesseract was not installed in the Ubuntu environment")
    shutil.copy2(tesseract, tess_bin / "tesseract")

    for source_dir, target_dir in (
        (PREFIX / "share/poppler", root / "vendor/share/poppler"),
        (PREFIX / "share/ghostscript", root / "vendor/ghostscript/share/ghostscript"),
        (PREFIX / "share/fonts", root / "vendor/share/fonts"),
    ):
        if source_dir.is_dir():
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)

    # The build host may provide fonts through Ubuntu's fonts-noto-cjk package
    # rather than Conda. Bundle the regular SC collection so the UI renders
    # Chinese even on a minimal Ubuntu installation with no CJK fonts.
    bundled_fonts = root / "vendor/share/fonts/opentype/noto"
    bundled_fonts.mkdir(parents=True, exist_ok=True)
    for style in ("Regular", "Medium", "Bold"):
        name = "NotoSansCJK-" + style + ".ttc"
        candidates = (PREFIX / "share/fonts/opentype/noto" / name,
                      Path("/usr/share/fonts/opentype/noto") / name)
        cjk_font = next((path for path in candidates if path.is_file()), None)
        if cjk_font is None:
            raise RuntimeError("Noto Sans CJK fonts are required; install Ubuntu package fonts-noto-cjk before building")
        shutil.copy2(cjk_font, bundled_fonts / name)
    cjk_license = Path("/usr/share/doc/fonts-noto-cjk/copyright")
    license_target = root / "licenses/fonts-noto-cjk"
    license_target.mkdir(parents=True, exist_ok=True)
    if cjk_license.is_file():
        shutil.copy2(cjk_license, license_target / "copyright")

    prepare_xft_tk()

    # Conda's generated fonts.conf embeds absolute build-machine paths. Replace
    # it with a relocatable config that searches system and bundled font dirs.
    font_config = root / "vendor/etc/fonts/fonts.conf"
    font_config.parent.mkdir(parents=True, exist_ok=True)
    font_config.write_text(
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
        '<fontconfig>\n'
        '  <dir>/usr/share/fonts</dir>\n'
        '  <dir prefix="relative">../../share/fonts</dir>\n'
        '  <dir prefix="xdg">fonts</dir>\n'
        '  <cachedir prefix="xdg">fontconfig</cachedir>\n'
        '</fontconfig>\n',
        encoding="utf-8",
    )
    tessdata = root / "vendor/tesseract/tessdata"
    tessdata.mkdir(parents=True)
    bundled = PREFIX / "share/tessdata"
    for path in bundled.glob("*") if bundled.is_dir() else ():
        if path.is_dir() and path.name == "configs":
            shutil.copytree(path, tessdata / path.name, dirs_exist_ok=True)
        elif path.is_file() and path.name in ("eng.traineddata", "chi_sim.traineddata", "pdf.ttf"):
            shutil.copy2(path, tessdata / path.name)
    for lang in ("eng", "chi_sim"):
        path = tessdata / (lang + ".traineddata")
        if not path.is_file():
            url = "https://github.com/tesseract-ocr/tessdata_fast/raw/4.1.0/" + path.name
            download(url, path)

    records = []
    for metadata in (PREFIX / "conda-meta").glob("*.json"):
        data = json.loads(metadata.read_text("utf-8"))
        source_dir = Path(data.get("link", {}).get("source", ""))
        license_dirs = [PREFIX / "share/doc" / (data["name"] + "-" + data["version"]), PREFIX / "licenses" / data["name"]]
        if source_dir.is_dir():
            license_dirs.insert(0, source_dir / "info/licenses")
        license_dir = root / "licenses/conda" / (data["name"] + "-" + data["version"])
        for candidate in license_dirs:
            if candidate.is_dir():
                shutil.copytree(candidate, license_dir, dirs_exist_ok=True)
        recipe_dir = source_dir / "info/recipe"
        if recipe_dir.is_dir():
            shutil.copytree(recipe_dir, license_dir / "recipe", dirs_exist_ok=True)
        record = {key: data.get(key) for key in ("name", "version", "build", "channel", "url", "license", "sha256")}
        record["license_files"] = [str(path.relative_to(root)) for path in license_dir.rglob("*") if path.is_file()] if license_dir.is_dir() else []
        records.append(record)
    (root / "licenses/THIRD_PARTY.txt").write_text(
        "Linux offline components are conda-forge packages listed with versions and URLs in components-linux.json. "
        "Their copyright and license files are included under licenses/conda when supplied by the package. "
        "Ubuntu Tcl/Tk package notices are under licenses/ubuntu-tk; Noto CJK font notices are under licenses/fonts-noto-cjk. "
        "Upstream source archives for FFmpeg, Ghostscript, Poppler, and Tesseract are under sources/. "
        "Qwen model files are licensed under Apache-2.0; see models/Qwen3.5-2B/LICENSE.\n",
        encoding="utf-8",
    )


def prepare_xft_tk():
    """Stage Ubuntu's Xft-enabled Tk, whose backend can render bundled TTFs."""
    cache = ROOT / ".toolchain/ubuntu-tk"
    downloads = cache / "debs"
    extracted = cache / "root"
    downloads.mkdir(parents=True, exist_ok=True)
    if not (extracted / "usr/lib/x86_64-linux-gnu/libtk8.6.so").is_file():
        subprocess.run(["apt", "download", "libtk8.6", "libtcl8.6", "tk8.6", "tcl8.6"],
                       cwd=downloads, check=True)
        extracted.mkdir(parents=True, exist_ok=True)
        for package in downloads.glob("*.deb"):
            subprocess.run(["dpkg-deb", "-x", str(package), str(extracted)], check=True)
    source_lib = extracted / "usr/lib/x86_64-linux-gnu"
    target_lib = STAGE / "vendor/system-tk/lib"
    target_lib.mkdir(parents=True, exist_ok=True)
    for name in ("libtk8.6.so", "libtcl8.6.so"):
        source = source_lib / name
        if not source.is_file():
            raise RuntimeError("Ubuntu Xft Tk package is missing " + name)
        shutil.copy2(source, target_lib / name)
    scripts = extracted / "usr/share/tcltk"
    for name in ("tk8.6", "tcl8.6"):
        source = scripts / name
        if not source.is_dir():
            raise RuntimeError("Ubuntu Tk package is missing Tcl scripts: " + str(source))
        shutil.copytree(source, STAGE / "vendor/system-tk" / name, dirs_exist_ok=True)
    for name in ("libtk8.6", "libtcl8.6", "tk8.6", "tcl8.6"):
        copyright_file = extracted / "usr/share/doc" / name / "copyright"
        if copyright_file.is_file():
            target = STAGE / "licenses/ubuntu-tk" / (name + ".copyright")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(copyright_file, target)


def add_models():
    lock = json.loads((ROOT / "packaging/windows/llama-lock.json").read_text("utf-8"))
    model_root = STAGE / "models/Qwen3.5-2B"
    model_root.mkdir(parents=True, exist_ok=True)
    for item in lock:
        if not item["name"].startswith("Qwen3.5"):
            continue
        cached = CACHE / item["name"]
        if not cached.is_file() or sha256(cached) != item["digest"]:
            cached = download(item["urls"], cached, item["digest"])
        output_name = {"Qwen3.5-2B-Q4_K_M.gguf": "Qwen3.5-2B-Q4_K_M.gguf",
                       "Qwen3.5-2B-mmproj-F16.gguf": "mmproj-F16.gguf",
                       "Qwen3.5-LICENSE": "LICENSE"}[item["name"]]
        shutil.copy2(cached, model_root / output_name)


def build_llama():
    lock = json.loads((ROOT / "packaging/windows/llama-lock.json").read_text("utf-8"))
    source_item = next(item for item in lock if item["name"] == "llama-b11669-source.tar.gz")
    source_archive = CACHE / source_item["name"]
    if not source_archive.is_file() or sha256(source_archive) != source_item["digest"]:
        source_archive = download(source_item["urls"], source_archive, source_item["digest"])
    source_root = ROOT / ".toolchain/llama-linux-source"
    if not source_root.is_dir():
        source_root.mkdir(parents=True, exist_ok=True)
        with tarfile.open(source_archive, "r:gz") as archive:
            archive.extractall(source_root, filter="data")
    source_dir = next(path for path in source_root.iterdir() if path.is_dir())
    build_dir = ROOT / ".toolchain/llama-linux-build"
    install_dir = STAGE / "vendor/llama.cpp/cpu"
    subprocess.run([
        "cmake", "-S", str(source_dir), "-B", str(build_dir),
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_INSTALL_PREFIX=" + str(install_dir),
        "-DGGML_NATIVE=ON", "-DLLAMA_BUILD_SERVER=ON", "-DLLAMA_BUILD_TESTS=OFF",
        "-DLLAMA_BUILD_EXAMPLES=OFF", "-DLLAMA_BUILD_TOOLS=ON",
    ], check=True)
    subprocess.run(["cmake", "--build", str(build_dir), "--config", "Release", "-j", "8", "--target", "llama-server"], check=True)
    candidates = list(build_dir.rglob("llama-server"))
    if not candidates:
        raise RuntimeError("llama.cpp did not produce llama-server")
    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidates[0], install_dir / "llama-server")
    bundled_libs = install_dir / "lib"
    bundled_libs.mkdir(parents=True, exist_ok=True)
    for path in (build_dir / "bin").glob("*.so*"):
        shutil.copy2(path, bundled_libs / path.name)
    license_file = next((path for path in source_dir.iterdir() if path.name.lower().startswith("license")), None)
    if license_file:
        shutil.copy2(license_file, STAGE / "licenses/llama.cpp-LICENSE")
    source_copy = STAGE / "sources/llama.cpp/llama-b11669-source.tar.gz"
    source_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_archive, source_copy)


def collect_libraries():
    """Copy only Conda shared libraries required by the bundled native tools."""
    roots = list((STAGE / "vendor/Library/bin").iterdir())
    roots += list((STAGE / "vendor/ghostscript/bin").iterdir())
    roots += list((STAGE / "vendor/tesseract/bin").iterdir())
    roots += list((STAGE / "vendor/llama.cpp/cpu").rglob("llama-server"))
    wanted: dict[Path, set[str]] = {}
    pending = list(roots)
    scanned: set[Path] = set()
    while pending:
        executable = pending.pop()
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = str(PREFIX / "lib") + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
        result = subprocess.run(["ldd", str(executable)], text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, check=False, env=env)
        for line in result.stdout.splitlines():
            match = re.search(r"=>\s+(/\S+)", line)
            if not match:
                continue
            resolved = Path(match.group(1))
            try:
                real = resolved.resolve(strict=True)
                real.relative_to(PREFIX.resolve())
            except (OSError, ValueError):
                continue
            names = wanted.setdefault(real, set())
            names.add(resolved.name)
            names.add(real.name)
            if real not in scanned:
                scanned.add(real)
                pending.append(real)
    library_root = STAGE / "vendor/lib"
    library_root.mkdir(parents=True, exist_ok=True)
    for source, names in wanted.items():
        for name in names:
            target = library_root / name
            if target.exists() or target.is_symlink():
                continue
            if name == source.name:
                shutil.copy2(source, target)
            else:
                target.symlink_to(source.name)


def split_executables():
    """Keep native child processes executable when PyInstaller extracts them."""
    if EXECUTABLES.exists():
        shutil.rmtree(EXECUTABLES)
    for relative in (
        "vendor/Library/bin/ffmpeg", "vendor/Library/bin/ffprobe",
        "vendor/Library/bin/pdftoppm", "vendor/Library/bin/pdftocairo",
        "vendor/Library/bin/pdfinfo", "vendor/ghostscript/bin/gs",
        "vendor/tesseract/bin/tesseract", "vendor/llama.cpp/cpu/llama-server",
    ):
        source = STAGE / relative
        if not source.is_file():
            continue
        target = EXECUTABLES / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        target.chmod(0o755)
        source.unlink()
        if relative.endswith("llama-server"):
            for duplicate in (STAGE / "vendor/llama.cpp/cpu").rglob("llama-server"):
                if duplicate != source:
                    duplicate.unlink()


def add_sources():
    """Include matching upstream sources for the four shipped CLI projects."""
    sources = STAGE / "sources"
    for package_name in ("ffmpeg", "ghostscript", "poppler", "tesseract"):
        metadata_path = next((path for path in (PREFIX / "conda-meta").glob(package_name + "-*.json")
                              if json.loads(path.read_text("utf-8")).get("name") == package_name), None)
        if not metadata_path:
            continue
        metadata = json.loads(metadata_path.read_text("utf-8"))
        package_dir = Path(metadata.get("link", {}).get("source", ""))
        recipe_dir = package_dir / "info/recipe"
        data = {}
        for name in ("recipe.yaml", "meta.yaml", "rendered_recipe.yaml"):
            recipe = recipe_dir / name
            if not recipe.is_file():
                continue
            with recipe.open(encoding="utf-8") as stream:
                candidate = yaml.safe_load(stream) or {}
            if candidate.get("source") or candidate.get("finalized_sources"):
                data = candidate
                break
        entries = data.get("source", [])
        entries = entries if isinstance(entries, list) else [entries]
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("folder") == "tessdata_fast" or entry.get("target_directory") == "tessdata_fast":
                continue
            url = entry.get("url")
            digest = entry.get("sha256")
            if not url or not digest:
                continue
            url = url.replace("${{ name }}", package_name).replace("${{ version }}", metadata["version"])
            if "{{ name }}" in url:
                url = url.replace("{{ name }}", package_name)
            if "{{ version }}" in url:
                url = url.replace("{{ version }}", metadata["version"])
            filename = url.rsplit("/", 1)[-1].split("?", 1)[0] or package_name + "-source.tar.gz"
            download(url, sources / package_name / filename, digest)
    for name in ("LICENSE", "README.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, STAGE / name)
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT
    ).decode("utf-8").split("\0")
    archive_path = sources / "OfficerTools-source.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in sorted(set(tracked)):
            if name and (ROOT / name).is_file():
                archive.write(ROOT / name, "OfficerTools/" + name)


def main():
    copy_runtime()
    add_models()
    build_llama()
    collect_libraries()
    add_sources()
    split_executables()
    records = []
    for metadata in (PREFIX / "conda-meta").glob("*.json"):
        data = json.loads(metadata.read_text("utf-8"))
        records.append({key: data.get(key) for key in ("name", "version", "build", "channel", "url", "license", "sha256")})
    for package in sorted((ROOT / ".toolchain/ubuntu-tk/debs").glob("*.deb")):
        fields = subprocess.check_output(["dpkg-deb", "-f", str(package), "Package", "Version", "Architecture"], text=True).splitlines()
        records.append({"name": fields[0], "version": fields[1], "architecture": fields[2],
                        "kind": "ubuntu-package", "sha256": sha256(package)})
    for path in sorted((STAGE / "models/Qwen3.5-2B").iterdir()):
        if path.is_file():
            records.append({"name": path.name, "version": "Qwen3.5-2B", "license": "Apache-2.0",
                            "sha256": sha256(path), "bytes": path.stat().st_size})
    for path in sorted((STAGE / "sources").rglob("*")):
        if path.is_file():
            records.append({"name": path.relative_to(STAGE).as_posix(), "kind": "upstream-source",
                            "sha256": sha256(path), "bytes": path.stat().st_size})
    for path in sorted(EXECUTABLES.rglob("*")):
        if path.is_file():
            records.append({"name": path.relative_to(EXECUTABLES).as_posix(), "kind": "linux-executable",
                            "sha256": sha256(path), "bytes": path.stat().st_size})
    (STAGE / "components-linux.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print("Linux one-file payload ready: " + str(STAGE), flush=True)


if __name__ == "__main__":
    main()
