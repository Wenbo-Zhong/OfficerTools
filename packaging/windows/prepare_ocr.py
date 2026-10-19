"""Stage a minimal Tesseract runtime, pinned models and redistribution materials."""
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pefile

from prepare_vendor import ROOT, CACHE, download, sha256, recipe_sources

PREFIX=ROOT/".toolchain/ocr-env"
STAGE=ROOT/".toolchain/release-ocr"
LOCK=Path(__file__).with_name("ocr-lock.json")


def prepare():
    CACHE.mkdir(parents=True,exist_ok=True)
    lock=json.loads(LOCK.read_text("utf-8"))
    if not (PREFIX/"conda-meta").exists():
        vendor_lock=json.loads(LOCK.with_name("vendor-lock.json").read_text("utf-8"))
        archive=download(**vendor_lock["micromamba"])
        executable=CACHE/"micromamba.exe"
        if not executable.exists():
            with tarfile.open(str(archive)) as stream:
                executable.write_bytes(stream.extractfile("Library/bin/micromamba.exe").read())
        explicit=CACHE/"ocr-explicit.txt"
        explicit.write_text("@EXPLICIT\n"+"\n".join(p["url"]+"#"+p["md5"] for p in lock)+"\n",encoding="utf-8")
        subprocess.run([str(executable),"create","--prefix",str(PREFIX),"--root-prefix",str(ROOT/".toolchain/mamba"),"--file",str(explicit),"--yes"],check=True)
    packages=[json.loads(p.read_text("utf-8")) for p in (PREFIX/"conda-meta").glob("*.json")]
    actual={p["name"]:p["sha256"] for p in packages}
    for p in lock:
        if actual.get(p["name"])!=p["sha256"]: raise RuntimeError("OCR environment differs from lock: "+p["name"])
    if STAGE.resolve().parent != (ROOT/".toolchain").resolve(): raise RuntimeError("Unexpected OCR staging path")
    if STAGE.exists(): shutil.rmtree(str(STAGE))
    binary_dir=PREFIX/"Library/bin"
    binaries={p.name.lower():p for p in binary_dir.iterdir() if p.suffix.lower() in (".exe",".dll")}
    selected={};queue=[binaries["tesseract.exe"]]
    while queue:
        path=queue.pop()
        if path.name.lower() in selected: continue
        selected[path.name.lower()]=path
        with pefile.PE(str(path),fast_load=True) as image:
            image.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]])
            for entry in list(getattr(image,"DIRECTORY_ENTRY_IMPORT",[]))+list(getattr(image,"DIRECTORY_ENTRY_DELAY_IMPORT",[])):
                candidate=binaries.get(entry.dll.decode("ascii").lower())
                if candidate: queue.append(candidate)
    runtime=STAGE/"vendor/tesseract"
    (runtime/"bin").mkdir(parents=True)
    for path in selected.values(): shutil.copy2(str(path),str(runtime/"bin"/path.name))
    tessdata=runtime/"tessdata"
    tessdata.mkdir()
    shutil.copytree(str(PREFIX/"Library/share/tessdata/configs"),str(tessdata/"configs"))
    model_records=[]
    for lang in ("eng","chi_sim"):
        path=PREFIX/"share/tessdata"/(lang+".traineddata")
        shutil.copy2(str(path),str(tessdata/path.name))
        model_records.append({"name":lang,"sha256":sha256(path),"bytes":path.stat().st_size,
            "url":"https://github.com/tesseract-ocr/tessdata_fast/blob/4.1.0/"+path.name})
    sources=STAGE/"sources/ocr";sources.mkdir(parents=True)
    records=[];jobs=[]
    for package in packages:
        if not any(Path(f).name.lower() in selected for f in package["files"] if f.lower().startswith("library/bin/")): continue
        info=Path(package["extracted_package_dir"])/"info"
        target=STAGE/"licenses/ocr"/(package["name"]+"-"+package["version"])
        shutil.copytree(str(info),str(target/"package-info"))
        record={k:package.get(k) for k in ("name","version","build","url","sha256","license")}
        record["sources"]=[]
        if package["name"] not in ("ucrt","vc14_runtime","vcomp14","vc"):
            entries=recipe_sources(info)
            if not entries: raise RuntimeError("Missing OCR source metadata: "+package["name"])
            for entry in entries:
                if "path" in entry: continue
                # Apache-licensed trained model files are supplied directly, rather
                # than adding the archive of every language to the release.
                if entry.get("folder")=="tessdata_fast": continue
                urls=entry["url"];url=urls[0] if isinstance(urls,list) else urls
                name=package["name"]+"-"+url.rsplit("/",1)[-1].split("?")[0]
                shared=ROOT/".toolchain/release-vendor/sources"/name
                reused=shared.is_file() and sha256(shared)==entry["sha256"]
                record["sources"].append({"name":name if reused else "ocr/"+name,"urls":urls,"digest":entry["sha256"]})
                if not reused: jobs.append((urls,name,entry["sha256"]))
        records.append(record)
    def fetch(job):
        path=download(*job);shutil.copy2(str(path),str(sources/path.name))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch,jobs))
    license_path=download("https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/LICENSE",
        "tessdata-fast-4.1.0-LICENSE","cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")
    shutil.copy2(str(license_path),str(tessdata/"LICENSE"))
    shutil.copy2(str(license_path),str(STAGE/"licenses/ocr/tessdata-fast-LICENSE.txt"))
    (sources/"MODELS.json").write_text(json.dumps(model_records,indent=2),encoding="utf-8")
    (sources/"README.txt").write_text("Tesseract 5.5.0; Apache-2.0. The unmodified tessdata_fast 4.1.0 eng/chi_sim model files are supplied in ../../vendor/tesseract/tessdata/. Their hashes and upstream URLs are in MODELS.json. Other languages are not bundled. Matching engine and library sources plus original build recipes/licenses accompany this runtime.\n",encoding="utf-8")
    (STAGE/"components-ocr.json").write_text(json.dumps(records,indent=2),encoding="utf-8")
    (STAGE/"READY").write_text(sha256(LOCK))
    print("OCR ready: {} binaries, English + Simplified Chinese".format(len(selected)),flush=True)


if __name__=="__main__": prepare()
