# Qwen 多语言备用识别

Windows 完整包内置 llama.cpp b11669（v0.7.0 源码提交 620d2225c）、Qwen3.5-2B Q4_K_M 权重和 F16 视觉投影文件，支持 Vulkan 或纯 CPU。Apple Silicon 的 macOS `.app` 在本机编译同版本 llama.cpp，内置相同模型及 Metal、OpenCL、CPU 后端。模型来自 Unsloth 对 Qwen 官方模型的 GGUF 转换，锁定版本与 SHA256，未自行训练或更改模型权重。

## 选择逻辑

| 引擎 | 行为 |
| --- | --- |
| auto | 已安装所选语言的 Tesseract 模型时使用 Tesseract，否则使用 Qwen |
| tesseract | 强制用 Tesseract，缺少模型会明确提示 |
| qwen | 强制用 Qwen |

语言默认 `chi_sim+eng`，保持中英文的轻量处理方式。可填 `日语`、`jpn`、`俄语`、`rus`、`法语`、`fra` 等；多语言可用 `+` 连接。语言填 `auto` 时直接由 Qwen 处理，适合不知道语种的情况。按语言选择回退与自动判断图片语言是两种不同操作，默认不会先对每张图执行大模型检测。

Windows 上 Qwen 的 `auto` 运行方式先尝试 Vulkan，失败后回退 CPU。Apple Silicon macOS 上依次尝试 Metal、OpenCL、CPU；失败的后端进程会关闭，成功后同一批后续页面复用该后端。也可手动选择可用的后端。macOS 构建在目标 Mac 本机编译 llama.cpp。

## 输出与限制

- 图片、PDF、屏幕 OCR 共用上述选择逻辑。PDF 的密码、页码范围、批量处理保持可用。
- Qwen 可导出文字，或把原页面图像与透明文字层组成可搜索 PDF。文字层按文本流放置，位置为估计，不等于原图的逐字字框；适合查找和复制，不能用于精确高亮与定位。
- Qwen 不导出 hOCR/TSV；这种输出需要对应语言的 Tesseract 模型。
- 模型输出可能误识别、补字或漏字，复杂版式及小语种应使用真实文档验收。超出输出长度的页面会报错，不将截断文本当作完整结果保存。
- 服务仅在本机 `127.0.0.1` 随机端口运行，使用随机访问密钥；不开放网页界面、不联网下载。任务结束、取消及程序正常退出时清理自身服务进程。
- CPU 可以运行，但内存占用及速度取决于文档、硬件与驱动。模型文件约 1.95 GB，不代表运行时仅需要这么多内存。

## 发布材料

Windows 包的 `vendor/llama.cpp/cpu/` 与 `vendor/llama.cpp/vulkan/` 只包含服务程序和实际依赖。macOS `.app` 的 `Contents/Resources/vendor/llama.cpp/` 含本机编译的 metal、opencl、cpu 服务程序。所有工具共用 `models/Qwen3.5-2B/`，模型权重和视觉投影文件与 Windows 锁定版本一致。

`packaging/windows/llama-lock.json` 记录下载地址与哈希；`prepare_llama.py` 可断点下载并校验。对应源码、许可证及组件记录随 ZIP 发布。模型与构建缓存受 `.gitignore` 排除，不推入源码仓库。

官方多模态文档：https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md
官方 OpenCL 文档：https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/OPENCL.md
模型转换仓库：https://huggingface.co/unsloth/Qwen3.5-2B-GGUF
