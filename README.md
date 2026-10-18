# OfficerTools

跨平台办公工具箱。功能按常见办公套件来组织：PDF、格式转换、图片、OCR、录屏截屏、文件和系统小工具。界面按显示器的真实 DPI 绘制，Windows 安装包声明了 Per-Monitor DPI，系统不会把窗口当位图放大。

本项目以 GNU GPL v3 授权，见 [LICENSE](LICENSE)。

## 运行

需要 Python 3.8 到 3.13。Windows 7 只能用 Python 3.8。

```text
pip install -r requirements.txt
python -m officertools
python -m officertools pdf-merge
python -m officertools pdf-merge --run files=a.pdf|b.pdf
```

## 打包

Windows：在仓库根目录执行 `powershell -ExecutionPolicy Bypass -File build_windows.ps1`。产物在 `dist/OfficerTools/`。`办公工具箱.exe` 是总入口，每个工具也是单独的 exe，可以单独拷走。安装包用 Python 3.8 生成。用 Python 3.13 打出来的 exe 会报 “Failed to load Python DLL python313.dll / 找不到指定的模块”，在 Windows 7 上无法启动。

macOS：把仓库拷到 Mac 后执行 `sh build_macos.sh`，得到一个 `dist/OfficerTools.app`。

Ubuntu：执行 `sh build_linux.sh`，得到 `dist/officertools`。

## 需要另外安装的程序

这些工具在对应程序存在时才会做完整转换：

- Ghostscript 或 Poppler：PDF 转图片、转黑白、纠偏、PDF OCR
- Tesseract（含 chi_sim）：图片、PDF、屏幕 OCR
- FFmpeg：音视频转换、屏幕录像、GIF、录音
- LibreOffice：带版式的办公文档转换
- 7-Zip：CHM 解包

图片转 PDF 默认按 300 DPI 嵌入原始像素。截屏和放大镜在完成 DPI 感知后按物理像素取样。

## 许可

Copyright (C) 2026 Wenbo Zhong

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
