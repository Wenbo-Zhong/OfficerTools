# 内置 OCR

Windows ZIP 包内置 Tesseract 5.5.0（Apache-2.0）及 tessdata_fast 4.1.0 的简体中文 `chi_sim`、英文 `eng` 模型，无需另外安装、配置 PATH 或联网下载。只打包这两种语言及运行时实际使用的 DLL，不带全部语言模型。

Apple Silicon macOS `.app` 同样内置 Tesseract、tessdata_fast 4.1.0 的 `chi_sim` 和 `eng` 模型，以及 Qwen3.5-2B。macOS 版 llama.cpp 在构建机器本地编译；自动后端按 Metal、OpenCL、CPU 顺序尝试。Apple 的 OpenCL 环境若未被 llama.cpp 识别为兼容设备，会跳过并继续回退。

## 使用

- 图片 OCR：多选图片或添加文件夹，支持多页 TIFF。默认导出 UTF-8 文字。
- PDF OCR：支持批量、打开密码及页码范围，默认同时导出文字和可搜索 PDF。可搜索 PDF 使用页面图像加识别文字层，不还原 Word 版式。
- 屏幕 OCR：点击“在屏幕上选择区域”，拖动框选后开始识别；留空区域识别全屏。
- 语言默认 `chi_sim+eng`；只识别英文可填 `eng`，简体中文可填 `chi_sim`。
- 页面分割 3 为自动版面、4 为单栏、6 为整块文字、7 为单行、11 为零散文字。
- `text` 导出文字；`both` / `searchable` 同时导出文字与可搜索 PDF；`hocr` / `tsv` 另外导出文字位置等结构化信息。

识别在本机进行，不向服务上传图片。识别结果可能有错，尤其是手写、低分辨率图片、复杂表格及版面，请校对。更多语言需自行添加兼容模型到 `vendor/tesseract/tessdata/`。

## 发布与验证

运行时放在 `vendor/tesseract/`；每个工具仍使用小型原生入口及共享主程序。引擎与依赖包版本、下载地址和哈希锁定于 `packaging/windows/ocr-lock.json`。许可证和原始构建材料随包位于 `licenses/ocr/`；对应引擎、库源码位于 `sources/ocr/` 或共享 `sources/`；模型版本、哈希及上游链接位于 `sources/ocr/MODELS.json`。

自动测试在空 PATH、错误的全局模型路径下验证真实中英文识别、搜索 PDF 的文字层、加密扫描 PDF、页码选择、屏幕区域调用、hOCR/TSV 和缺少语言提示。屏幕测试使用生成的样本图，未采集用户屏幕内容。

官方说明：https://tesseract-ocr.github.io/tessdoc/Installation.html
模型说明：https://tesseract-ocr.github.io/tessdoc/Data-Files.html
