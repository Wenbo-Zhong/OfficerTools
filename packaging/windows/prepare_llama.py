"""Stage pinned CPU/Vulkan llama.cpp servers and the offline Qwen vision model."""
import json
import shutil
import tarfile
import zipfile
import subprocess
from pathlib import Path

import pefile
from prepare_vendor import ROOT, CACHE, download, sha256

LOCK=Path(__file__).with_name("llama-lock.json")
STAGE=ROOT/".toolchain/release-llama"


def fetch(item):
    CACHE.mkdir(parents=True,exist_ok=True)
    path=CACHE/item["name"]
    if path.exists() and sha256(path)==item["digest"]: return path
    curl=shutil.which("curl.exe")
    if not curl: return download(**item)
    temporary=path.with_name(path.name+".part")
    subprocess.run([curl,"--silent","--show-error","--fail","--location","--retry","5","--retry-all-errors",
                    "--continue-at","-","--output",str(temporary),item["urls"]],check=True)
    if sha256(temporary)!=item["digest"]:
        temporary.unlink()
        raise RuntimeError("SHA256 mismatch: "+item["name"])
    temporary.replace(path)
    return path


def prepare():
    lock=json.loads(LOCK.read_text("utf-8"))
    cached={item["name"]:fetch(item) for item in lock}
    if STAGE.resolve().parent != (ROOT/".toolchain").resolve(): raise RuntimeError("Unexpected llama staging folder")
    if STAGE.exists(): shutil.rmtree(str(STAGE))
    STAGE.mkdir(parents=True)
    notices=STAGE/"licenses/llama.cpp";notices.mkdir(parents=True)
    runtime_records=[]
    for backend in ("cpu","vulkan"):
        archive_path=cached["llama-b11669-bin-win-"+backend+"-x64.zip"]
        temporary=ROOT/".toolchain"/("llama-extract-"+backend)
        temporary.mkdir(exist_ok=True)
        with zipfile.ZipFile(str(archive_path)) as archive:
            # Official archives are flat. Read only names, never arbitrary archive paths.
            for name in archive.namelist():
                if "/" in name or "\\" in name: continue
                if name.lower().endswith((".dll",".exe")):
                    (temporary/name).write_bytes(archive.read(name))
                elif name.startswith(("LICENSE","COPYING","NOTICE")):
                    (notices/(backend+"-"+name)).write_bytes(archive.read(name))
        binaries={path.name.lower():path for path in temporary.glob("*") if path.suffix.lower() in (".dll",".exe")}
        # Microsoft runtime DLLs already have matching notices in the shared vendor stage.
        for folder in (ROOT/".toolchain/release-vendor/vendor/Library/bin",ROOT/".toolchain/release-ocr/vendor/tesseract/bin"):
            for path in folder.glob("*.dll"):
                if path.name.lower().startswith(("vcruntime","msvcp","concrt")): binaries.setdefault(path.name.lower(),path)
        queue=[binaries["llama-server.exe"]]+[path for name,path in binaries.items() if name.startswith("ggml-cpu-")]
        if backend=="vulkan": queue.append(binaries["ggml-vulkan.dll"])
        selected={}
        while queue:
            path=queue.pop()
            if path.name.lower() in selected: continue
            selected[path.name.lower()]=path
            with pefile.PE(str(path),fast_load=True) as image:
                image.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]])
                for entry in list(getattr(image,"DIRECTORY_ENTRY_IMPORT",[]))+list(getattr(image,"DIRECTORY_ENTRY_DELAY_IMPORT",[])):
                    candidate=binaries.get(entry.dll.decode("ascii").lower())
                    if candidate: queue.append(candidate)
        folder=STAGE/"vendor/llama.cpp"/backend;folder.mkdir(parents=True)
        for path in selected.values(): shutil.copy2(str(path),str(folder/path.name))
        runtime_records.append({"backend":backend,"files":{p.name:sha256(p) for p in folder.iterdir()}})
    model=STAGE/"models/Qwen3.5-2B";model.mkdir(parents=True)
    shutil.copy2(str(cached["Qwen3.5-2B-Q4_K_M.gguf"]),str(model/"Qwen3.5-2B-Q4_K_M.gguf"))
    shutil.copy2(str(cached["Qwen3.5-2B-mmproj-F16.gguf"]),str(model/"mmproj-F16.gguf"))
    shutil.copy2(str(cached["Qwen3.5-LICENSE"]),str(model/"LICENSE"))
    shutil.copy2(str(cached["Qwen3.5-LICENSE"]),str(notices/"Qwen3.5-APACHE-2.0.txt"))
    sources=STAGE/"sources/llama.cpp";sources.mkdir(parents=True)
    source=cached["llama-b11669-source.tar.gz"]
    shutil.copy2(str(source),str(sources/source.name))
    with tarfile.open(str(source)) as archive:
        for member in archive.getmembers():
            if member.isfile() and Path(member.name).name in ("LICENSE","LICENSE.md","COPYING","NOTICE"):
                relative=Path(*Path(member.name).parts[1:])
                dest=notices/relative;dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(archive.extractfile(member).read())
    record={"llama_cpp":"b11669 / v0.7.0","model":"Qwen3.5-2B Q4_K_M + F16 vision projector",
            "model_publisher":"unsloth (GGUF conversion of Qwen/Qwen3.5-2B)","downloads":lock,"runtimes":runtime_records}
    (STAGE/"components-llama.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
    (sources/"README.txt").write_text("llama.cpp MIT source and original dependency notices accompany this release. The Qwen GGUF model and vision projector are in ../../models/Qwen3.5-2B/ (Apache-2.0). Exact model revision, binary/source URLs and SHA256 digests: ../../components-llama.json. CPU and Vulkan runtimes contain only the server and its required/dynamically selected backend DLLs. OpenCL is not included in this Windows package. GPU drivers are supplied by the operating system/device vendor.\n",encoding="utf-8")
    (STAGE/"READY").write_text(sha256(LOCK),encoding="ascii")
    print("llama.cpp CPU/Vulkan + offline Qwen3.5-2B vision model ready",flush=True)


if __name__=="__main__": prepare()
