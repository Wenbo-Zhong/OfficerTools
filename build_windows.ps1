# One shared runtime, tiny native executables for individual tools.
# Build the 64-bit Windows 10+ package with Python 3.12.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Python = Join-Path $PSScriptRoot ".toolchain\py312\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
& $Python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "The Windows release must be built with Python 3.12. Install it to .toolchain\py312 and run again."
}
& $Python -X utf8 -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Build stopped." }
& $Python -X utf8 -m pip install 'PyYAML>=6,<7'
if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }
& $Python -X utf8 packaging\windows\prepare_vendor.py
if ($LASTEXITCODE -ne 0) { throw "Vendor binaries or matching sources are incomplete. Build stopped." }
& $Python -X utf8 packaging\windows\prepare_ocr.py
if ($LASTEXITCODE -ne 0) { throw "OCR runtime, models or source materials are incomplete." }
& $Python -X utf8 packaging\windows\prepare_llama.py
if ($LASTEXITCODE -ne 0) { throw "Local Qwen model or llama.cpp runtimes are incomplete." }
& $Python -X utf8 packaging\windows\prepare_python_sources.py
if ($LASTEXITCODE -ne 0) { throw "Python component sources are incomplete. Build stopped." }
$compiler = Get-Command gcc -ErrorAction SilentlyContinue
if (-not $compiler) { throw "MinGW-w64 gcc is required to build the small native tool launchers." }
$launcherOutput = Join-Path $PSScriptRoot '.toolchain\tool-launcher.exe'
& $compiler.Source -mwindows -Os -s -nostdlib -ffreestanding -fno-builtin '-Wl,-e,launcher_start' -finput-charset=UTF-8 packaging\windows\tool_launcher.c -o $launcherOutput -lkernel32 -luser32
if ($LASTEXITCODE -ne 0) { throw "Native tool launcher build failed." }
$distRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'dist'))
$buildRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'build'))
if ($distRoot -ne (Join-Path $PSScriptRoot 'dist') -or $buildRoot -ne (Join-Path $PSScriptRoot 'build')) {
    throw "Unexpected build output paths"
}
if (Test-Path -LiteralPath $distRoot) {
    # A running app or Explorer can hold its working directory open. Clear files
    # first, retaining any empty directories Windows will not release yet.
    Get-ChildItem -LiteralPath $distRoot -Recurse -File -Force | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop
    }
    Get-ChildItem -LiteralPath $distRoot -Recurse -Directory -Force |
        Sort-Object { $_.FullName.Length } -Descending | ForEach-Object {
            if (-not (Get-ChildItem -LiteralPath $_.FullName -Force | Select-Object -First 1)) {
                try { Remove-Item -LiteralPath $_.FullName -ErrorAction Stop } catch { }
            }
        }
}
if (Test-Path -LiteralPath $buildRoot) { Remove-Item -LiteralPath $buildRoot -Recurse -Force }
$releaseOutput = Join-Path $distRoot 'OfficerTools-release'
New-Item -ItemType Directory -Path $releaseOutput -Force | Out-Null
& $Python -X utf8 packaging\windows\executable_icons.py
if ($LASTEXITCODE -ne 0) { throw "Executable icon generation failed." }
& $Python -m PyInstaller --noconfirm --clean --distpath $releaseOutput packaging\windows\officertools.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed. Build stopped." }
& $Python -X utf8 packaging\windows\executable_icons.py --output $releaseOutput --template $launcherOutput
if ($LASTEXITCODE -ne 0) { throw "Tool entry point generation failed." }
$mainExecutableName = (-join [char[]](0x529e,0x516c,0x5de5,0x5177,0x7bb1)) + '.exe'
Remove-Item -LiteralPath (Join-Path $releaseOutput $mainExecutableName) -Force
& $Python -X utf8 packaging\windows\package_release.py $releaseOutput
if ($LASTEXITCODE -ne 0) { throw "Release assembly failed." }
