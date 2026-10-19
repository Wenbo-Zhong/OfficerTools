"""Download the Windows-matched Qwen model and build local llama.cpp backends."""
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "packaging/windows/llama-lock.json"
OCR_LOCK = ROOT / "packaging/macos/ocr-model-lock.json"
CACHE = ROOT / ".toolchain/macos-cache"
SOURCE = ROOT / ".toolchain/macos-src/llama.cpp-b11669"
BUILD = ROOT / ".toolchain/macos-builds"
STAGE = ROOT / ".toolchain/release-macos"


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def fetch(item):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / item["name"]
    if path.is_file() and digest(path) == item["digest"]:
        return path
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError("curl is required to download the Qwen model and llama.cpp source")
    partial = path.with_suffix(path.suffix + ".part")
    subprocess.run([curl, "--fail", "--location", "--retry", "20", "--retry-all-errors",
                    "--speed-limit", "1024", "--speed-time", "30",
                    "--continue-at", "-", "--output", str(partial), item["urls"]], check=True)
    if digest(partial) != item["digest"]:
        partial.unlink()
        raise RuntimeError("SHA256 mismatch for " + item["name"])
    partial.replace(path)
    return path


def build_backend(name, metal=False, opencl=False):
    build = BUILD / name
    args = [
        "cmake", "-S", str(SOURCE), "-B", str(build),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DGGML_BACKEND_DL=OFF",
        "-DGGML_NATIVE=ON",
        "-DGGML_METAL=" + ("ON" if metal else "OFF"),
        "-DGGML_METAL_EMBED_LIBRARY=ON",
        "-DGGML_OPENCL=" + ("ON" if opencl else "OFF"),
        # Apple's framework implements OpenCL 1.2; 2.0 headers expose the SVM
        # declarations used by llama.cpp without linking unavailable 2.1/3.0 APIs.
        "-DGGML_OPENCL_TARGET_VERSION=200",
        "-DGGML_OPENCL_USE_ADRENO_KERNELS=OFF",
        "-DGGML_OPENCL_EMBED_KERNELS=ON",
        "-DLLAMA_BUILD_SERVER=ON",
        "-DLLAMA_BUILD_TESTS=OFF",
        "-DLLAMA_BUILD_EXAMPLES=OFF",
    ]
    if opencl:
        brew = shutil.which("brew")
        if not brew:
            raise RuntimeError("OpenCL headers are needed. Install Homebrew and run: brew install opencl-headers")
        prefix = subprocess.run([brew, "--prefix", "opencl-headers"], check=True,
                                 stdout=subprocess.PIPE, text=True).stdout.strip()
        include = Path(prefix) / "include"
        if not (include / "CL/cl.h").is_file():
            raise RuntimeError("OpenCL headers are missing. Run: brew install opencl-headers")
        args.append("-DOpenCL_INCLUDE_DIR=" + str(include))
    subprocess.run(args, check=True)
    subprocess.run(["cmake", "--build", str(build), "--config", "Release",
                    "--target", "llama-server", "--parallel",
                    str(max(1, min(8, os.cpu_count() or 4)))], check=True)
    executable = build / "bin/llama-server"
    if not executable.is_file():
        raise RuntimeError("llama-server was not produced for " + name)
    target = STAGE / "vendor/llama.cpp" / name / "llama-server"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, target)


def prepare_tesseract():
    brew = shutil.which("brew")
    if not brew:
        raise RuntimeError("Homebrew is needed to collect the macOS Tesseract runtime")
    prefix = subprocess.run([brew, "--prefix", "tesseract"], check=True,
                            stdout=subprocess.PIPE, text=True).stdout.strip()
    binary = Path(prefix) / "bin/tesseract"
    license_file = Path(prefix) / "LICENSE"
    if not binary.is_file() or not license_file.is_file():
        raise RuntimeError("Install Tesseract first: brew install tesseract")
    target_binary = STAGE / "tesseract-bin/tesseract"
    target_binary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, target_binary)
    data = STAGE / "vendor/tesseract/tessdata"
    data.mkdir(parents=True, exist_ok=True)
    licenses = STAGE / "licenses/tesseract"
    licenses.mkdir(parents=True, exist_ok=True)
    shutil.copy2(license_file, licenses / "LICENSE")
    lock = json.loads(OCR_LOCK.read_text(encoding="utf-8"))
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError("curl is required to download Tesseract language data")
    for language, item in lock["models"].items():
        path = CACHE / ("tessdata-fast-4.1.0-" + language + ".traineddata")
        if not path.is_file() or digest(path) != item["sha256"]:
            subprocess.run([curl, "--fail", "--location", "--retry", "5", "--retry-all-errors",
                            "--output", str(path), item["url"]], check=True)
        if digest(path) != item["sha256"]:
            raise RuntimeError("SHA256 mismatch for Tesseract model " + language)
        shutil.copy2(path, data / (language + ".traineddata"))
    license_url = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/LICENSE"
    license_cache = CACHE / "tessdata-fast-4.1.0-LICENSE"
    if not license_cache.is_file():
        subprocess.run([curl, "--fail", "--location", "--retry", "5", "--retry-all-errors",
                        "--output", str(license_cache), license_url], check=True)
    shutil.copy2(license_cache, data / "LICENSE")


def prepare():
    if os.name != "posix" or os.uname().sysname != "Darwin" or os.uname().machine != "arm64":
        raise RuntimeError("This macOS release build requires an Apple Silicon Mac")
    if not shutil.which("cmake"):
        raise RuntimeError("CMake is required. Install it with Homebrew or add it to PATH.")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    items = {item["name"]: item for item in lock}
    source_item = items["llama-b11669-source.tar.gz"]
    archive = fetch(source_item)
    if not SOURCE.is_dir():
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "r:gz") as bundle:
            bundle.extractall(SOURCE.parent, filter="data")
        extracted = SOURCE.parent / "llama.cpp-b11669"
        if extracted != SOURCE and extracted.exists():
            extracted.rename(SOURCE)
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    models = STAGE / "models/Qwen3.5-2B"
    models.mkdir(parents=True)
    for source_name, target_name in (
        ("Qwen3.5-2B-Q4_K_M.gguf", "Qwen3.5-2B-Q4_K_M.gguf"),
        ("Qwen3.5-2B-mmproj-F16.gguf", "mmproj-F16.gguf"),
        ("Qwen3.5-LICENSE", "LICENSE"),
    ):
        shutil.copy2(fetch(items[source_name]), models / target_name)
    licenses = STAGE / "licenses/llama.cpp"
    licenses.mkdir(parents=True)
    shutil.copy2(SOURCE / "LICENSE", licenses / "LICENSE")
    sources = STAGE / "sources/llama.cpp"
    sources.mkdir(parents=True)
    shutil.copy2(archive, sources / archive.name)
    prepare_tesseract()
    build_backend("metal", metal=True)
    build_backend("opencl", opencl=True)
    build_backend("cpu")
    print("Prepared Qwen3.5-2B and llama.cpp Metal/OpenCL/CPU runtimes", flush=True)


if __name__ == "__main__":
    prepare()
