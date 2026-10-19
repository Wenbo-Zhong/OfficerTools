# OfficerTools

跨平台办公工具箱。功能按常见办公套件来组织：PDF、格式转换、图片、OCR、录屏截屏、文件和系统小工具。界面按显示器的真实 DPI 绘制，Windows 安装包声明了 Per-Monitor DPI，系统不会把窗口当位图放大。

本项目以 GNU AGPL v3 或更新版本授权，见 [LICENSE](LICENSE)。第三方授权和源码材料见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

界面提供深色和浅色两套配色，启动时跟随系统，并每 3 秒检查主题变化；无法读取系统设置时默认浅色。切换主题会保留已打开工具的输入、日志和滚动位置。Windows 读取应用主题设置，macOS 读取系统外观，Linux 读取 GNOME 的颜色方案设置，其他环境使用浅色。

## 运行

需要 Python 3.8 到 3.13。Windows 7 只能用 Python 3.8。

```text
pip install -r requirements.txt
python -m officertools
python -m officertools pdf-merge
python -m officertools pdf-merge --run files=a.pdf|b.pdf
```

## 打包

Windows：在仓库根目录执行 `powershell -ExecutionPolicy Bypass -File build_windows.ps1`，需要 Python 3.8 和 MinGW-w64 GCC。每次构建先清理旧输出，最终只保留 `dist/OfficerTools-release/`，内含 `OfficerTools/` 和完整发布包 `OfficerTools-Windows-x64.zip`；`build/` 只保留当前构建目录。重新构建前请关闭正在运行的旧版程序。`办公工具箱.exe` 保存共用运行环境，各工具 EXE 是仅依赖 Windows 系统 DLL 的原生启动器，不再重复打包 Python 或转换依赖。请保留完整目录结构，各工具启动器需要根目录的主程序；使用内置组件时还需要 `vendor` 文件夹。对外分发时请保留完整的 `sources` 和 `licenses`。发布包内置 Ghostscript、Poppler 和 FFmpeg，优先使用内置组件，无需配置 PATH。主程序仍用 Python 3.8 构建，但内置组件面向现代 64 位 Windows，整包尚未验证 Windows 7 兼容性。

构建脚本会按 `packaging/windows/vendor-lock.json` 下载并校验组件及对应源码，收集许可证、补丁和构建材料。首次构建需要网络和足够的磁盘空间；组件缓存位于 `.toolchain/`。

程序目录根部仅保留总入口，独立工具按 `tools/类别/工具名.exe` 整理，例如 `tools/PDF/PDF合并.exe`。分类目录中的工具会自动查找根目录共享的组件、许可证和源码文件夹。

macOS：把仓库拷到 Mac 后执行 `sh build_macos.sh`，得到一个 `dist/OfficerTools.app`。

Ubuntu：执行 `sh build_linux.sh`，得到 `dist/officertools`。

## 需要另外安装的程序

这些工具在对应程序存在时才会做完整转换：

- Ghostscript 或 Poppler：Windows 完整包已内置；其他平台需安装，用于 PDF 转图片、转黑白、纠偏、PDF OCR
- Tesseract：Windows 完整包已内置引擎及简体中文、英文模型；其他平台需安装
- FFmpeg：Windows 完整包已内置；其他平台需安装，用于音视频转换、屏幕录像、GIF、录音
- 文档转换组件：带版式的办公文档转换，需单独安装并配置可执行文件搜索路径
- 7-Zip：CHM 解包

图片转 PDF 默认按 300 DPI 嵌入原始像素。截屏和放大镜在完成 DPI 感知后按物理像素取样。

## 非 OCR 功能补齐

工具数增至 74 个。新增 PDF 页面编排（排序、复制、插入空白页）、单页切分、添加链接。
PDF 纠偏支持批量 PDF/TIFF、密码、页码、角度范围、保留文字或重建扫描页、裁白边；黑白转换提供自动阈值、手动阈值、抖动和灰度。
水印支持图片、平铺、位置和角度；PDF 阅读显示实际页面；Word/HTML 转换保留更多字体及图片信息。
通用任务在后台执行，可取消、调整队列顺序和选择输出位置；录屏支持区域与可用音频设备，停止时会完成 MP4 封装。
截图标注增加多种图形、文字、颜色和撤销；PDF417、透明图片压缩、幻灯片播放和科学计算已补齐常用能力。
详细变更、验证与尚未对齐的项目见 `docs/非OCR功能对齐-2026-10-18.md`。复杂 Word 排版、文件夹监控和部分高级编辑仍有差距。

Windows 完整包的图片、PDF、屏幕 OCR 可离线运行，无需安装识别程序或设置 PATH。默认语言 `chi_sim+eng`，也可填 `chi_sim` 或 `eng`；支持自动版面、整块文字、单行或零散文字。PDF OCR 支持密码、页码范围、批量任务，默认同时输出 UTF-8 文本及可搜索 PDF；图片支持多页 TIFF，屏幕支持框选区域。还可输出 hOCR/TSV 文字位置信息。可搜索 PDF 以页面图像加识别文字层组成，识别文字应校对。模型及许可材料在 `vendor/tesseract/tessdata/`，引擎与依赖源码在 `sources/ocr/`。

## Qwen 多语言备用 OCR

Windows 完整包另带 llama.cpp 的 Vulkan/CPU 运行时，以及 Qwen3.5-2B Q4_K_M 和 F16 视觉投影文件，运行时不下载模型、不上传文档。两份模型合计约 1.95 GB，集中放在 `models/Qwen3.5-2B/`，各工具 EXE 不重复携带。构建时按 `packaging/windows/llama-lock.json` 下载并校验；模型、缓存和发布文件不提交到 Git。

- `engine=auto`：有对应的 Tesseract 语言模型就使用它，缺少时自动使用 Qwen。
- 语言填 `日语` / `jpn`、`俄语` / `rus` 等可触发相应判断；填 `auto` 表示不确定语言，直接由 Qwen 识别。默认 `chi_sim+eng` 仍走已安装的中英文模型，并不会先检测图片的实际语言。
- `engine=qwen` 可强制使用 Qwen；`engine=tesseract` 不会回退。
- `backend=auto` 优先 Vulkan，无法完成时回退 CPU；也可指定 `vulkan` 或 `cpu`。Vulkan 需要可用显卡驱动；实际速度因硬件与驱动而异，CPU 也可运行。本 Windows 包不含主要面向 Adreno 的 OpenCL 后端。
- Qwen 支持文本与可搜索 PDF；它没有可靠的逐字坐标，因此可搜索文字层位置为估计，只适合检索/复制，不用于精确定位；hOCR/TSV 请使用有对应语言模型的 Tesseract。

推理服务只监听本机回环地址，按任务启动并在完成、取消或正常退出时关闭。Qwen 使用当前页面图像作为文档内容，识别结果需校对；语言覆盖不代表所有语种与版面的准确率相同。详见 `docs/Qwen备用OCR.md`。

## 许可

Copyright (C) 2026 Wenbo Zhong

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
