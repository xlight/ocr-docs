---
name: ocr-docs
description: Convert Word/PDF documents (including scanned Chinese books) to clean Markdown. Use whenever the user asks to convert documents to Markdown, OCR a scanned PDF, or process Chinese special-education/reference documents. Runs fully offline via local CLI.
license: MIT
metadata:
  author: ocr-docs
  version: "0.1.0"
---

# ocr-docs：文档转规范 Markdown

将 Word（docx/doc）、PDF（含扫描版中文书籍）转换为规范的 Markdown，支持段落、标题层级与表格结构。面向中文教育/特教文档做了垂直增强（错字修正、封面页保护、术语统一）。

## 触发场景

- 用户要求把 .docx / .doc / .pdf 转成 Markdown
- 用户提供**扫描版 PDF**（无文本层），要求提取文字/转格式
- 用户要求处理中文教育、特教类文档的批量转换
- 用户想将案例/评估 Markdown 整理为 Dify 知识库输入（预处理）

## 安装检查

```bash
ocr-docs --help        # 已安装则显示帮助
pip install ocr-docs   # 基础 CLI（普通文档转换）
pip install "ocr-docs[scanned]"   # + 扫描版 PDF（Docling + RapidOCR）
```

> 也可用 skills.sh / marketplace 安装（见 README 完整安装三通道）。

## 核心用法

**普通文档转换**：

```bash
ocr-docs convert 输入.docx -o 输出.md
ocr-docs convert 输入.pdf -o 输出.md        # 文本型 PDF
ocr-docs convert ./目录 -o ./输出目录/      # 目录递归批量
```

**扫描版 PDF（OCR + 版面分析）**：

```bash
ocr-docs convert --scanned 扫描书.pdf -o 输出.md
ocr-docs convert --scanned 扫描书.pdf --front-matter-pages 4 -o 输出.md
#                                        ↑ 前 4 页（封面/版权）逐行保护
```

**案例→Dify 知识库预处理**：

```bash
ocr-docs prep 案例/markdown -o 案例/markdown/prep
# 输出：kb_case{case,assessment,handout} + kb_rule + dify_config.md + prep_report.json
```

**常用参数**：

| 参数 | 说明 |
|------|------|
| `--scanned` | 扫描模式（OCR） |
| `--ocr-engine rapidocr\|ocrmac` | 指定 OCR 后端（默认 rapidocr；ocrmac 仅 macOS） |
| `--front-matter-pages N` | 前置页（封面/版权）数，逐行输出保护 |
| `--no-enhance` | 跳过中文增强（错字修正/术语统一） |

**退出码**：0 成功 / 1 转换失败 / 2 参数错误。

## 错误恢复

- `缺少 pandoc` → 安装 pandoc（`brew install pandoc` 或 `apt install pandoc`）
- `无文本层（扫描件）` → 改用 `--scanned`
- `扫描转换尚未就绪` → Docling 依赖安装受阻（Intel mac 无 docling-parse wheel）；请在 Linux/Docker 环境运行扫描转换
- `unknown OCR backend` → 检查 `--ocr-engine` 取值（rapidocr / ocrmac）

## 输出说明

- 普通路径：pandoc/mupdf 直转 + 中文增强
- 扫描路径：Docling 版面分析（标题 #/##/### 层级、段落合并、表格保留）+ 中文增强
- 文件就地输出到 `-o` 指定位置，无隐藏产物目录

## 注意

- 扫描模式首次运行 RapidOCR 会加载内置 ONNX 模型（随包分发，无需额外下载）；Docling 版面模型首次运行需联网下载
- 敏感文档请确认输出不被上传（本工具全部本地处理，无任何上传）