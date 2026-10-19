# Third-party software in the Windows release

OfficerTools is Copyright (C) 2026 Wenbo Zhong and is distributed under
GNU Affero General Public License version 3 or later (AGPL-3.0-or-later).
See `LICENSE`. This release's application source is included in
`sources/OfficerTools-source.zip`.

The complete release includes the following independently executed components:

| Component | Version | License | Upstream |
| --- | --- | --- | --- |
| Ghostscript | 10.08.0 | AGPL-3.0-or-later, with upstream exceptions and third-party notices | https://ghostscript.com/ |
| Poppler / pdftoppm | 26.09.0 | GPL-2.0-or-later; see per-file terms | https://poppler.freedesktop.org/ |
| FFmpeg (GPL build, shared libraries) | 9.0.2 | GPL-3.0-or-later | https://ffmpeg.org/ |
| PyMuPDF / MuPDF | 1.24.11 / 1.24.10 | AGPL-3.0 and per-file terms | https://github.com/pymupdf/PyMuPDF |
| ReportLab | 4.2.5 | BSD | https://www.reportlab.com/ |
| python-docx | 1.1.2 | MIT | https://github.com/python-openxml/python-docx |
| pdf417gen | 0.8.1 | MIT | https://github.com/ihabunek/pdf417-py |
| Tesseract | 5.5.0 | Apache-2.0 | https://github.com/tesseract-ocr/tesseract |
| tessdata_fast (eng, chi_sim only) | 4.1.0 | Apache-2.0 | https://github.com/tesseract-ocr/tessdata_fast |
| llama.cpp | b11669, v0.7.0 source commit 620d2225c | MIT and bundled dependency notices | https://github.com/ggml-org/llama.cpp |
| Qwen3.5-2B, Q4_K_M GGUF + F16 visual projector | Unsloth conversion revision f6d5376be1edb4d416d56da11e5397a961aca8ae | Apache-2.0 | https://huggingface.co/unsloth/Qwen3.5-2B-GGUF |

Copyright in these components belongs to their respective authors. The project
license does not replace or remove their license terms. No upstream endorsement
is implied. The release contains no `--enable-nonfree` FFmpeg build.

Matching upstream source archives accompany the binaries in `sources/`.
The added Python PDF/layout/barcode dependencies and their source hashes are in
`sources/python-packages/`; their supplied licenses are collected under
`licenses/python-packages/`. The matching MuPDF source archive is supplied
separately alongside PyMuPDF, whose setup.py records the upstream version and
build configuration.
OCR engine/library sources, original build recipes and notices are in
`sources/ocr/` and `licenses/ocr/`. The unmodified English and Simplified Chinese
trained model files are included directly in `vendor/tesseract/tessdata/`;
their hashes and versioned upstream links are in `sources/ocr/MODELS.json`.
The release does not contain the other languages from the training-data archive.
llama.cpp source and build files are in `sources/llama.cpp/`. Its MIT license,
vendored dependency notices and the binary distribution's LLVM OpenMP notice
are in `licenses/llama.cpp/`. Microsoft runtime notices remain in their shared
vendor license folders. Qwen model artifacts and their license are under
`models/Qwen3.5-2B/`; exact binary/model/source URLs and SHA256 digests are in
`components-llama.json` and the application's `packaging/windows/llama-lock.json`.
The GGUF files are a quantized conversion of Qwen/Qwen3.5-2B, not a new model
trained by OfficerTools. No upstream endorsement is implied.
For conda-forge binaries, the complete packaged build recipes, local inputs,
patches and dependency/compiler metadata accompany them in
`licenses/<package-version>/package-info/`. Exact versions, binary package URLs,
source URLs and source SHA256 hashes are recorded in `components.json`.
Retain all of these materials when distributing the release. The Ghostscript
binary is extracted without modification from the official AGPL installer;
its corresponding source distribution contains build instructions and licenses.

Dependent libraries keep their original licenses, including GPL, LGPL, BSD,
MIT, Apache and other upstream terms. Their notices and build metadata are
preserved alongside the sources. Shared libraries remain replaceable.
Microsoft runtime DLLs are redistributable components with their original
license terms, not relicensed as AGPL. Their supplied notices are retained.

Python, Tcl/Tk and Python package notices are in `licenses/`. The PyInstaller
bootloader's license exception is included with its notices. Fonts and CMap
data retain their own notices. The complete portable release targets modern
64-bit Windows; compatibility of bundled native components with Windows 7 has
not been established.

This package is supplied without warranty, as described in the applicable
licenses. Source and build scripts for OfficerTools are included so recipients
can inspect, modify, rebuild and redistribute it under the AGPL terms.

Individual tool EXEs are native launchers compiled without the C runtime and
import only Windows system DLLs. They delegate to the shared OfficerTools
application; Python and conversion dependencies are not embedded in each
launcher. Their complete C source and GCC build command are included in the
application source archive.
