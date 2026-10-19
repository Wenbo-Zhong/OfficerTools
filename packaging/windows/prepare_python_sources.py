"""Fetch exact upstream sources for the added PDF/layout dependencies."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / ".toolchain/python-sources"
PACKAGES = {"PyMuPDF":"1.24.11", "python-docx":"1.1.2", "reportlab":"4.2.5",
            "pdf417gen":"0.8.1", "lxml":"6.1.3", "chardet":"5.2.0", "pydicom":"2.4.4"}


def prepare():
    TARGET.mkdir(parents=True, exist_ok=True)
    cached_path=ROOT / "packaging/windows/python-source-lock.json"
    cached=json.loads(cached_path.read_text("utf-8"))
    records = []
    for name, version in PACKAGES.items():
        previous=next((item for item in cached if item["name"]==name and item["version"]==version),None)
        if previous:
            artifact={"filename":previous["file"],"url":previous["url"],"digests":{"sha256":previous["sha256"]}}
        else:
            with urllib.request.urlopen("https://pypi.org/pypi/{}/{}/json".format(name, version), timeout=60) as response:
                metadata = json.load(response)
            artifact = next(item for item in metadata["urls"] if item["packagetype"] == "sdist")
        path = TARGET / artifact["filename"]
        expected = artifact["digests"]["sha256"]
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            print("Downloading", artifact["filename"], flush=True)
            with urllib.request.urlopen(artifact["url"], timeout=60) as response:
                path.write_bytes(response.read())
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Source digest mismatch: " + str(path))
        records.append({"name":name,"version":version,"url":artifact["url"],"sha256":expected,"file":path.name})
    # PyPI's PyMuPDF sdist does not embed MuPDF; its setup.py pins 1.24.10.
    url="https://mupdf.com/downloads/archive/mupdf-1.24.10-source.tar.gz"
    expected="939285b5f97caf770fd46cbe7e6cc3a695ab19bb5bfaf5712904549cef390b7b"
    path=TARGET/"mupdf-1.24.10-source.tar.gz"
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        with urllib.request.urlopen(url,timeout=60) as response:
            path.write_bytes(response.read())
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise RuntimeError("MuPDF source digest mismatch")
    records.append({"name":"MuPDF","version":"1.24.10","url":url,"sha256":expected,"file":path.name})
    (TARGET / "python-source-components.json").write_text(json.dumps(records,indent=2),encoding="utf-8")


if __name__ == "__main__":
    prepare()
