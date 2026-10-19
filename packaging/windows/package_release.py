"""Assemble the complete redistributable folder and solid archive after PyInstaller."""
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / ".toolchain/release-vendor"
TARGET = (Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "dist") / "OfficerTools"


def digest(path):
    value=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1048576),b""):
            value.update(chunk)
    return value.hexdigest()


def assemble():
    # Fail the build if a tool entry ever starts carrying a bundled runtime again.
    import pefile
    sys.path.insert(0, str(ROOT))
    from officertools.catalog import TOOLS
    for tool in TOOLS:
        entry = TARGET / "tools" / tool.category / (tool.exe + ".exe")
        with pefile.PE(str(entry)) as image:
            # Multi-size icon artwork is data, not a duplicated application runtime.
            icon_bytes = sum(section.SizeOfRawData for section in image.sections
                             if section.Name.rstrip(b"\0") == b".rsrc")
            if entry.stat().st_size - icon_bytes > 16384:
                raise RuntimeError("Tool launcher unexpectedly contains runtime data: " + str(entry))
            resources = getattr(image, "DIRECTORY_ENTRY_RESOURCE", None)
            if not resources or {item.id for item in resources.entries} != {3, 14}:
                raise RuntimeError("Launcher must contain only icon resources: " + str(entry))
            imports = {item.dll.decode().lower() for item in image.DIRECTORY_ENTRY_IMPORT}
            if not imports <= {"kernel32.dll", "user32.dll"}:
                raise RuntimeError("Unexpected launcher dependency: " + str(imports))
    lock = ROOT / "packaging/windows/vendor-lock.json"
    if not (STAGE / "READY").exists() or (STAGE / "READY").read_text() != hashlib.sha256(lock.read_bytes()).hexdigest():
        raise RuntimeError("Run prepare_vendor.py successfully before assembling a release")
    for name in ("vendor", "sources", "licenses"):
        shutil.copytree(str(STAGE / name), str(TARGET / name), dirs_exist_ok=True)
    python_sources=ROOT / ".toolchain/python-sources"
    if not (python_sources / "python-source-components.json").is_file():
        raise RuntimeError("Run prepare_python_sources.py before packaging")
    shutil.copytree(str(python_sources),str(TARGET / "sources/python-packages"),dirs_exist_ok=True)
    ocr_stage=ROOT/".toolchain/release-ocr"
    ocr_lock=ROOT/"packaging/windows/ocr-lock.json"
    if not (ocr_stage/"READY").is_file() or (ocr_stage/"READY").read_text()!=hashlib.sha256(ocr_lock.read_bytes()).hexdigest():
        raise RuntimeError("Run prepare_ocr.py before assembling the release")
    for name in ("vendor","sources","licenses"):
        shutil.copytree(str(ocr_stage/name),str(TARGET/name),dirs_exist_ok=True)
    components=json.loads((STAGE/"components.json").read_text("utf-8"))
    components.extend(json.loads((ocr_stage/"components-ocr.json").read_text("utf-8")))
    llama_stage=ROOT/".toolchain/release-llama"
    llama_lock=ROOT/"packaging/windows/llama-lock.json"
    if not (llama_stage/"READY").is_file() or (llama_stage/"READY").read_text()!=digest(llama_lock):
        raise RuntimeError("Run prepare_llama.py before assembling the release")
    for name in ("vendor","models","sources","licenses"):
        shutil.copytree(str(llama_stage/name),str(TARGET/name),dirs_exist_ok=True)
    shutil.copy2(str(llama_stage/"components-llama.json"),str(TARGET/"components-llama.json"))
    components.append({"name":"llama.cpp","version":"b11669","license":"MIT","sources":[{"name":"llama.cpp/llama-b11669-source.tar.gz"}]})
    components.append({"name":"Qwen3.5-2B-GGUF","version":"f6d5376be1edb4d416d56da11e5397a961aca8ae","license":"Apache-2.0","sources":[]})
    (TARGET/"components.json").write_text(json.dumps(components,indent=2),encoding="utf-8")
    for name in ("LICENSE", "README.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(str(ROOT / name), str(TARGET / name))
    # The current working sources, including uncommitted changes, accompany the binary.
    files = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=str(ROOT)).decode("utf-8").split("\0")
    with zipfile.ZipFile(str(TARGET / "sources/OfficerTools-source.zip"), "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(files)):
            if name and (ROOT / name).is_file():
                archive.write(str(ROOT / name), "OfficerTools/" + name)
    # Preserve notices for Python packages used by the frozen runtime, including
    # the PyInstaller bootloader's GPL exception. Build-only notices may also appear.
    for dist in importlib.metadata.distributions():
        label = dist.metadata["Name"] + "-" + dist.version
        for relative in dist.files or []:
            if any(token in relative.name.lower() for token in ("license", "copying", "notice")):
                path = Path(dist.locate_file(relative))
                if path.is_file():
                    dest = TARGET / "licenses/python-packages" / label / str(relative).replace("../", "")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(path), str(dest))
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copy2(str(python_license), str(TARGET / "licenses/Python-LICENSE.txt"))
    for path in (Path(sys.base_prefix) / "tcl").rglob("license.terms"):
        dest = TARGET / "licenses/tcl-tk" / path.relative_to(Path(sys.base_prefix) / "tcl")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(path), str(dest))
    (TARGET / "sources/README.txt").write_text(
        "OfficerTools: AGPL-3.0-or-later; complete current application sources are in OfficerTools-source.zip.\n"
        "Ghostscript: upstream 10.08.0 source archive, unmodified official Windows binary.\n"
        "Tesseract OCR and its dependencies: ocr/; English and Simplified Chinese model details: ocr/MODELS.json.\n"
        "llama.cpp: llama.cpp/; Qwen weights and vision projector: ../models/Qwen3.5-2B/, exact revisions/hashes: ../components-llama.json.\n"
        "PyMuPDF (including its matching MuPDF source), python-docx, reportlab, pdf417gen and their added dependencies: python-packages/.\n"
        "FFmpeg, Poppler and their bundled libraries: matching upstream source archives are in this folder.\n"
        "Exact package versions, source URLs and SHA256 digests are in ../components.json.\n"
        "Conda-forge build recipes, patches and compiler/build dependency metadata are preserved under\n"
        "../licenses/<package-version>/package-info/recipe (including rendered recipes).\n"
        "Build using the recorded conda-build/rattler-build recipe and target win-64 with the recorded compiler.\n"
        "Microsoft runtime redistributables retain their own licenses; no ownership or open-source claim is made for them.\n"
        "Redistribute this complete package, including sources, notices and licenses.\n", encoding="utf-8")
    manifest = {}
    for path in sorted(TARGET.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.json":
            manifest[path.relative_to(TARGET).as_posix()] = digest(path)
    (TARGET / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    archive = TARGET.parent / "OfficerTools-Windows-x64.zip"
    with zipfile.ZipFile(str(archive), "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as output:
        for path in sorted(TARGET.rglob("*")):
            if path.is_file():
                # Upstream source archives are already compressed; store them as-is.
                method = zipfile.ZIP_STORED if path.name.endswith((".gz", ".xz", ".bz2", ".zip", ".7z")) else zipfile.ZIP_DEFLATED
                output.write(str(path), path.relative_to(TARGET.parent).as_posix(), compress_type=method)
    print("Release: " + str(archive), flush=True)


if __name__ == "__main__":
    assemble()
