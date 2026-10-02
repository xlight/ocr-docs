# ocr-docs

中文教育/特教文档 → 规范 Markdown 的转换工具（CLI + Agent 技能）。

**定位**：通用 PDF→Markdown 工具（nutrient / MinerU / Docling）已成熟，本项目不与之正面竞争通用场景；差异化在于 **开源（MIT）+ 中文教育文档垂直增强**——高置信错字修正、封面/版权页保护、可扩展特教术语表，并打包为 AI Agent 可直接使用的技能（SKILL.md）。

## 架构（薄壳复用）

**大部分能力直接引入社区成熟方案，不重复造轮子；只自研数据资产与薄胶水层。**

| 功能 | 引入社区 | 自研 |
|------|----------|------|
| 版面分析（标题/段落/表格） | Docling | — |
| 扫描 OCR | RapidOCR（默认，简体中文实测最优）/ OcrMac（macOS 可选）| — |
| 普通文档转换 | pandoc / textutil / PyMuPDF | — |
| CLI 框架 | typer | — |
| Agent 技能分发 | skills.sh / marketplace 生态 | — |
| 中文错字词表（45 条） | — | ✅ 本项目核心 |
| 前置页（封面/版权）保护 | — | ✅ 本项目核心 |
| 特教术语表 | — | ✅ 本项目核心 |
| CLI 编排 + SKILL.md | — | ✅ 本项目 |

默认 OCR 后端选择有社区实测支撑：RapidOCR 简体中文 Han CER 0.054（优于 OcrMac 0.097 / Tesseract 0.116），且模型随包分发、离线可用。

## 安装（三通道）

### 1. skills.sh（AI Agent / 跨 agent 通用，推荐）

```bash
npx skills add xlight/ocr-docs
```

works with Claude Code / Codex / Cursor / Zed 等所有支持 SKILL.md 的 agent。

### 2. Claude Code Marketplace

```bash
/plugin marketplace add xlight/ocr-docs
/plugin install ocr-docs@ocr-docs
```

### 3. PyPI（人类用户 / CI）

```bash
pip install ocr-docs
# 扫描版 PDF 转换需要额外依赖
pip install "ocr-docs[scanned]"
# macOS 可选 OCR 后端（高速、免下载）
pip install "ocr-docs[ocrmac]"
```

## 快速开始

```bash
# 普通文档转换（docx / doc / 文本型 PDF）
ocr-docs convert 输入.docx -o 输出.md
ocr-docs convert ./docs -o ./out           # 目录递归批量

# 扫描版 PDF（OCR + 版面分析）
ocr-docs convert --scanned 扫描书.pdf -o 输出.md
ocr-docs convert --scanned 扫描书.pdf --front-matter-pages 4 -o 输出.md
```

## 工作流

### 1. 普通文档（有文本层）

```mermaid
flowchart LR
    A[docx / doc / 文本型 PDF] --> B[pandoc / textutil / PyMuPDF]
    B --> C[中文增强层<br/>错字修正 + 术语统一]
    C --> D[Markdown]
```

### 2. 扫描文档（纯图片 PDF）

```mermaid
flowchart LR
    A[扫描版 PDF] --> B[渲染页面 PNG]
    B --> C[OCR 后端<br/>RapidOCR 默认 / OcrMac 可选]
    C --> D[Docling 版面分析<br/>标题层级 + 段落 + 表格]
    D --> E[前置页保护 + 中文增强]
    E --> F[Markdown]
```

## 参数速查

| 参数 | 说明 | 默认 |
|------|------|------|
| `convert <输入>` | 输入文件或目录 | 必填 |
| `-o, --output` | 输出文件或目录 | 输入同名 .md |
| `--scanned` | 扫描模式（OCR）| 关 |
| `--ocr-engine` | `rapidocr`（跨平台）/ `ocrmac`（macOS）| rapidocr |
| `--front-matter-pages N` | 前置页保护数 | 0 |
| `--no-enhance` | 跳过中文增强 | 关 |

## 中文增强层（zh_enhance）

| 模块 | 作用 | 配置 |
|------|------|------|
| `typo_fixes.py` | 45 条高置信错字修正（整词替换，不误伤正常文本）| 内置 |
| `terms.yaml` | 特教术语统一 | 编辑文件或 `OCR_DOCS_TERMS_FILE` 指向自定义 YAML |
| `front_matter.py` | 封面/版权页逐行保护，不做段落合并 | `--front-matter-pages N` |

## 开发

```bash
pip install -e ".[dev]"
pytest                # 单元测试（不依赖 Docling，可完整运行）
```

CI（`.github/workflows/ci.yml`）：单元测试（Python 3.10-3.12）+ 可选集成测试（需 docling 环境，手动触发）。

## 已知限制（⚠️ 重要）

1. **扫描转换依赖 Docling**：Intel (x86_64) macOS 无 `docling-parse` 预编译 wheel，本机扫描转换暂不可用；请在 **Linux / Docker / arm64 macOS** 环境运行 `--scanned`。需配合 `pip install "ocr-docs[scanned]"`。
2. **OCR 引擎**：RapidOCR 模型随包分发（离线可用）；OcrMac 仅 macOS。
3. 图片内文字 / 复杂表格图片依赖 Docling 能力，效果因源文档而异。
4. OCR 单字错字无法全部预置修正（词表覆盖高频项），**人名/机构名/数据等敏感内容建议对照原文档核对**。

## 路线图

- [ ] Docling 扫描管线接入（任务 5，待环境——见上）
- [ ] Spike 完整报告 + OcrMac 对比（任务 1.2/1.3）
- [ ] `query` 命令：转换结果 BM25 检索（借鉴 nutrient，二期）
- [ ] 发布到 GitHub + PyPI 正式版

## 许可证

MIT