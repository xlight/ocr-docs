---
name: ocr-docs
description: Convert Word/PDF documents (including scanned Chinese books) to clean Markdown, preprocess cases for Dify knowledge base, and fix OCR errors with an LLM. Use whenever the user asks to convert documents to Markdown, OCR a scanned PDF, process Chinese special-education/reference documents, or clean up OCR garbled text in split documents.
license: MIT
metadata:
  author: ocr-docs
  version: "0.3.0"
---

# ocr-docs：文档转规范 Markdown + Dify 知识库预处理 + LLM 修缮

将 Word（docx/doc）、PDF（含扫描版中文书籍）转换为规范的 Markdown，支持段落、标题层级与表格结构。面向中文教育/特教文档做了垂直增强（错字修正、封面页保护、术语统一）。拆分结果可直接预处理成 Dify 知识库输入，并对 OCR 噪声做 LLM 修缮。

## 触发场景

- 用户要求把 .docx / .doc / .pdf 转成 Markdown
- 用户提供**扫描版 PDF**（无文本层），要求提取文字/转格式
- 用户要求处理中文教育、特教类文档的批量转换
- 用户想将案例/评估 Markdown 整理为 Dify 知识库输入（预处理）
- 用户说拆出来的文档有 OCR 乱码/错字，想用 LLM 修缮（refine）

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
# 输出：kb_case/<源文档>/ + kb_rule/<源文档>/ + dify_config.md + prep_report.json
```

**LLM 修缮（refine）**：见下方专节。

## LLM 修缮（refine）：修正 OCR 错字/乱码

拆分出的 markdown 常带扫描书 OCR 噪声（形近字、乱码、漏字）。修缮流程是：
**CLI 把文档拆成段级任务 → AI（agent）逐段修缮 → CLI 校验拼装**。

```mermaid
flowchart LR
    A["prep 输出目录"] --> B["ocr-docs refine\n拆段级任务清单"]
    B --> C["AI 逐段修缮\n（agent 用自己的 LLM，有什么用什么）"]
    C --> D["ocr-docs refine-apply\n安全校验 + 拼装写回"]
    D --> E["refined/ 目录\n交下一步（Dify 知识库等）"]
```

### 关键约定（务必遵守）

1. **CLI 不调用任何 LLM**。`ocr-docs refine` 只做拆分，`refine-apply` 只做校验拼装；
   真正的修缮由 agent 完成（读任务清单 → 用自己的 LLM 逐段改错字 → 写回
   “refined” 字段）。不需要 API key，不需要在 CLI 里配任何 LLM 通道。
2. **不要用 `visionary-server` 批量调用**：它复用网页登录 token，批量高频请求
   会被风控，**有封号风险**。仅限少量人工抽查时用（如 <3 段）。批量修缮用
   agent 自己的 LLM 工具即可。
3. **先抽样，后全量**：默认 `--limit 3~5` 验证效果，确认无误再全量。
4. **元数据头必须原样保留**：`【类型】…【对应工具】` 块不动，只修正文。

### refine 安全规则（tamper_guard，AI 修缮结果都要经过这层校验）

AI 修缮结果若触发任一规则，整段回退原文（宁可漏修，不可篡改）：

| 规则 | 说明 | 示例（应回退） |
|------|------|----------------|
| 长度膨胀 | 扩写/压缩 >20% | "短文"→"这是一段很长的扩写……" |
| 年份篡改 | 4 位年份集变化 | "2013年9月"→"2018年9月" |
| 删除汉字 | 任何汉字被删 | "作者："→"作："、漏字 |
| 删除中文标点 | 全角标点被删 | "学习，写作业"→"学习写作业" |
| 汉字擦除 | 汉字改为空格/符号 | "很远"→"很 "、"稳定"→"定" |
| 结构丢失 | # 标题/**/列表符号丢弃 | "### 标题"→"标题" |

误删示例（LLM 常见陷阱）：`考虑→考`、`代币制→币制`、`每一刻→一刻`、`作者→作`。
这些必须被回退。

### Agent 工作流（skill 主流程）

1. **定位输入**：`prep/` 输出目录（kb_case/kb_rule）或用户给的 md 目录。
2. **拆任务**：`ocr-docs refine <dir> -o refine_tasks.json --limit 5`（抽样）
   或全量（去掉 --limit）。
3. **AI 逐段修缮**：逐条读 refine_tasks.json 的 tasks，对每段 text 用自己的
   LLM 修正错字，把结果写入该条的 "refined" 字段。
   （可参考 Python 工具：ocrdocs.refine 的 tamper_guard / split_at_sentence_boundaries）
4. **校验拼装**：`ocr-docs refine-apply refine_tasks.json -o refined/`。
   命令会套 tamper_guard：删字/改年份/丢结构的段自动回退原文，并报告回退数。
5. **diff 抽查**：检查修缮前后差异，确认只改了错字（如 `基木→基本`、
   `期未→期末`），无误删/改年份/结构损坏。
6. **确认后全量**：质量可接受才全量跑（拆全部任务 → AI 修缮 → apply）。
7. **汇报**：给出修缮统计（修了几段/回退了几段）+ 抽查 diff 示例。

### Python 参考（agent 直接 import 复用）

```python
from ocrdocs.refine import (
    build_refine_tasks,       # 拆段级任务清单
    apply_refine_edits,       # AI 结果拼装 + 安全校验
    split_at_sentence_boundaries,  # 句子边界分段
    tamper_guard,             # 安全校验（返回原文或修缮文本）
)
```

## 常用参数

| 参数 | 说明 |
|------|------|
| `--scanned` | 扫描模式（OCR） |
| `--ocr-engine rapidocr\|ocrmac` | 指定 OCR 后端（默认 rapidocr；ocrmac 仅 macOS） |
| `--front-matter-pages N` | 前置页（封面/版权）数，逐行输出保护 |
| `--no-enhance` | 跳过中文增强（错字修正/术语统一） |
| `refine --limit N` | 抽样：只拆前 N 个文件为修缮任务 |
| `refine --seg-len N` | 段长（默认 400，文本 LLM 可放宽） |
| `refine-apply --no-guard` | 跳过安全校验（不建议） |

**退出码**：0 成功 / 1 转换失败 / 2 参数错误。

## 错误恢复

- `缺少 pandoc` → 安装 pandoc（`brew install pandoc` 或 `apt install pandoc`）
- `无文本层（扫描件）` → 改用 `--scanned`
- `扫描转换尚未就绪` → Docling 依赖安装受阻（Intel mac 无 docling-parse wheel）；请在 Linux/Docker 环境运行扫描转换
- `unknown OCR backend` → 检查 `--ocr-engine` 取值（rapidocr / ocrmac）
- `refine 未配置 LLM（缺 REFINE_LLM_API_KEY）` → 不需要 key：修缮由 agent 用自己的 LLM 完成，CLI 只拆任务/拼装
- `refine-apply 报找不到源文件` → 检查 refine_tasks.json 中的 `_src_dir` 是否指向真实 prep 输出目录
- `visionary upload 报错` → 网页通道稳定性问题，不要依赖；批量修缮用 agent 自己的 LLM

## 输出说明

- 普通路径：pandoc/mupdf 直转 + 中文增强
- 扫描路径：Docling 版面分析（标题 #/##/### 层级、段落合并、表格保留）+ 中文增强
- 文件就地输出到 `-o` 指定位置，无隐藏产物目录

## 注意

- 扫描模式首次运行 RapidOCR 会加载内置 ONNX 模型（随包分发，无需额外下载）；Docling 版面模型首次运行需联网下载
- 敏感文档请确认输出不被上传（本工具全部本地处理，无任何上传）
- **LLM 修缮不要用 visionary 批量调用（封号风险）**；用正式 API key 或 agent 自己的 LLM