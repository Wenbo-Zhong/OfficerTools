"""Collect pinned binaries, dependency licenses, build recipes and matching sources.

Requires PyYAML and pefile in the build environment. Uses an isolated conda prefix.
"""
import hashlib
import json
import shutil
import subprocess
import tarfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pefile
import yaml

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".toolchain/vendor"
PREFIX = ROOT / ".toolchain/poppler-env"
STAGE = ROOT / ".toolchain/release-vendor"
LOCK = Path(__file__).with_name("vendor-lock.json")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def download(urls, name, digest):
    dest = CACHE / name
    if dest.exists() and sha256(dest) == digest:
        return dest
    errors = []
    candidates = [urls] if isinstance(urls, str) else list(urls)
    for url in list(candidates):
        if "ftp.gnu.org/pub/gnu/" in url:
            candidates.insert(0, "https://mirrors.kernel.org/gnu/" + url.split("/pub/gnu/", 1)[1])
        if "savannah.gnu.org/releases/freetype/" in url:
            filename = url.rsplit("/", 1)[1]
            candidates.insert(0, "https://downloads.sourceforge.net/project/freetype/freetype2/2.14.3/" + filename)
            candidates.insert(0, "https://download-mirror.savannah.gnu.org/releases/freetype/" + filename)
        if "downloads.xiph.org/releases/" in url:
            candidates.insert(0, "https://ftp.osuosl.org/pub/xiph/releases/" + url.split("/releases/", 1)[1])
    for url in candidates:
        try:
            url = url.replace("http://", "https://", 1)
            request = urllib.request.Request(url, headers={"User-Agent": "OfficerTools-release/1.0"})
            temp = dest.with_suffix(dest.suffix + ".part")
            with urllib.request.urlopen(request, timeout=45) as source, temp.open("wb") as target:
                shutil.copyfileobj(source, target)
            if sha256(temp) != digest:
                raise RuntimeError("SHA256 mismatch: " + url)
            temp.replace(dest)
            print("Downloaded " + name, flush=True)
            return dest
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("Cannot fetch {}: {}".format(name, "; ".join(errors)))


def dependency_files():
    binaries = {p.name.lower(): p for p in (PREFIX / "Library/bin").glob("*") if p.suffix.lower() in (".exe", ".dll")}
    selected = {}
    queue = [binaries[name] for name in ("pdftoppm.exe", "ffmpeg.exe", "ffprobe.exe")]
    while queue:
        path = queue.pop()
        if path.name.lower() in selected:
            continue
        selected[path.name.lower()] = path
        with pefile.PE(str(path), fast_load=True) as image:
            image.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"], pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]])
            for entry in list(getattr(image, "DIRECTORY_ENTRY_IMPORT", [])) + list(getattr(image, "DIRECTORY_ENTRY_DELAY_IMPORT", [])):
                candidate = binaries.get(entry.dll.decode("ascii").lower())
                if candidate:
                    queue.append(candidate)
    return selected


def recipe_sources(info):
    path = info / "recipe/rendered_recipe.yaml"
    if not path.exists():
        path = info / "recipe/meta.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = data.get("source") or data.get("finalized_sources") or data.get("finalized_cache_sources") or data.get("recipe", {}).get("source") or []
    return sources if isinstance(sources, list) else [sources]


def prepare():
    CACHE.mkdir(parents=True, exist_ok=True)
    if STAGE.resolve().parent != (ROOT / ".toolchain").resolve():
        raise RuntimeError("Unexpected staging directory")
    if STAGE.exists():
        shutil.rmtree(str(STAGE))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if not (PREFIX / "conda-meta").exists():
        archive = download(**lock["micromamba"])
        executable = CACHE / "micromamba.exe"
        with tarfile.open(str(archive)) as stream:
            executable.write_bytes(stream.extractfile("Library/bin/micromamba.exe").read())
        explicit = CACHE / "vendor-explicit.txt"
        explicit.write_text("@EXPLICIT\n" + "\n".join(p["url"] + "#" + p["md5"] for p in lock["conda"]) + "\n", encoding="utf-8")
        subprocess.run([str(executable), "create", "--prefix", str(PREFIX), "--root-prefix", str(ROOT / ".toolchain/mamba"), "--file", str(explicit), "--yes"], check=True)
    installed = [json.loads(p.read_text(encoding="utf-8")) for p in (PREFIX / "conda-meta").glob("*.json")]
    actual = {p["name"]: p["sha256"] for p in installed}
    for package in lock["conda"]:
        if actual.get(package["name"]) != package["sha256"]:
            raise RuntimeError("Vendor environment differs from lock: " + package["name"])
    installer = download(**lock["ghostscript_binary"])
    seven = CACHE / "7zip/7z.exe"
    if not seven.exists():
        reduced = download(**lock["7zr"])
        setup = download(**lock["7zip"])
        subprocess.run([str(reduced), "x", str(setup), "-o" + str(seven.parent), "-y"], check=True, stdout=subprocess.DEVNULL)
    extracted = CACHE / "ghostscript"
    if not (extracted / "bin/gswin64c.exe").exists():
        subprocess.run([str(seven), "x", str(installer), "-o" + str(extracted), "-y"], check=True, stdout=subprocess.DEVNULL)
    for subdir in ("bin", "lib", "Resource", "iccprofiles", "doc"):
        shutil.copytree(str(extracted / subdir), str(STAGE / "vendor/ghostscript" / subdir), dirs_exist_ok=True)
    source = download(**lock["ghostscript_source"])
    sources_dir = STAGE / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(sources_dir / source.name))
    licenses = STAGE / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(source)) as archive:
        (licenses / "Ghostscript-LICENSE.txt").write_bytes(archive.extractfile("ghostscript-10.08.0/LICENSE").read())
        (licenses / "AGPL-3.0.txt").write_bytes(archive.extractfile("ghostscript-10.08.0/doc/COPYING").read())
    selected = dependency_files()
    bin_dir = STAGE / "vendor/Library/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for path in selected.values():
        shutil.copy2(str(path), str(bin_dir / path.name))
    shutil.copytree(str(PREFIX / "share/poppler"), str(STAGE / "vendor/share/poppler"), dirs_exist_ok=True)
    if (PREFIX / "Library/etc/fonts").exists():
        shutil.copytree(str(PREFIX / "Library/etc/fonts"), str(STAGE / "vendor/Library/etc/fonts"), dirs_exist_ok=True)
    chosen = [{"name": "ghostscript", "version": "10.08.0", "license": "AGPL-3.0-or-later",
               "url": lock["ghostscript_binary"]["urls"], "sha256": lock["ghostscript_binary"]["digest"],
               "sources": [lock["ghostscript_source"]]}]
    jobs = []
    for package in installed:
        owns_binary = any(Path(f).name.lower() in selected for f in package["files"] if f.lower().startswith("library/bin/"))
        if not owns_binary and package["name"] != "poppler-data":
            continue
        info = Path(package["extracted_package_dir"]) / "info"
        target = licenses / (package["name"] + "-" + package["version"])
        shutil.copytree(str(info), str(target / "package-info"), dirs_exist_ok=True)
        record = {k: package.get(k) for k in ("name", "version", "build", "url", "sha256", "license")}
        record["sources"] = []
        if package["name"] not in ("ucrt", "vc14_runtime", "vcomp14", "vc"):
            sources = recipe_sources(info)
            if not sources:
                raise RuntimeError("Missing source metadata: " + package["name"])
            for entry in sources:
                if "path" in entry:
                    # Local patches/build inputs are included in package-info/recipe.
                    continue
                urls = entry["url"]
                url = urls[0] if isinstance(urls, list) else urls
                name = package["name"] + "-" + url.rsplit("/", 1)[-1].split("?")[0]
                record["sources"].append({"urls": urls, "digest": entry["sha256"], "name": name})
                jobs.append((urls, name, entry["sha256"]))
        chosen.append(record)
    def fetch(job):
        path = download(*job)
        shutil.copy2(str(path), str(sources_dir / path.name))
    failures = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch, job) for job in jobs]
        for future in futures:
            try:
                future.result()
            except Exception as exc:
                failures.append(str(exc))
    (STAGE / "components.json").write_text(json.dumps(chosen, indent=2, ensure_ascii=False), encoding="utf-8")
    if failures:
        raise RuntimeError("Source collection incomplete:\n" + "\n".join(failures))
    (STAGE / "READY").write_text(sha256(LOCK), encoding="ascii")
    print("Vendor bundle ready: {} binaries, {} packages".format(len(selected), len(chosen)), flush=True)


if __name__ == "__main__":
    prepare()
