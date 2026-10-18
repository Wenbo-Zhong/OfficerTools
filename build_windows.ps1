# One shared runtime, one exe per tool. Double-click a tool exe to open that tool.
# Build the Windows 7 package with Python 3.8. Python 3.9 and later do not run on Windows 7.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Python = Join-Path $PSScriptRoot ".toolchain\py38\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
& $Python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 8) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Windows 7 needs this package built with Python 3.8. Install it to .toolchain\py38 and run again."
}
& $Python -m pip install -r requirements.txt
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
& $Python -m PyInstaller --noconfirm --clean packaging\windows\officertools.spec
& $Python -c "import shutil; from pathlib import Path; from officertools.catalog import TOOLS; root=Path('dist')/'OfficerTools'; base=Path('dist')/'办公工具箱.exe'; root.mkdir(parents=True, exist_ok=True); shutil.copy2(str(base), str(root/'办公工具箱.exe')); base=root/'办公工具箱.exe';
assert base.is_file(), base
copied=[]
for tool in TOOLS:
    dest=root/(tool.exe+'.exe')
    shutil.copy2(str(base), str(dest))
    copied.append(dest.name)
print('copied', len(copied), 'tool exes into', root)"
