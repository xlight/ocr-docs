"""验收助手：断言式检查输出是否符合预期（供组 8 验收）。

检查项：
- 结构：目录结构、文件名模板
- 内容：无 HTML/锚点/图片残留、元数据头齐全
- 脱敏：对照映射后无真实名泄漏
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ocrdocs.prep.config_loader import load_anonymize_map


# ---------- 书内案例清单加载 ----------

def load_case_inventory() -> list[dict]:
    """加载 case_inventory.yaml（书内案例清册）。"""
    import yaml

    path = Path(__file__).parent / "config" / "case_inventory.yaml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data.get("case_inventory", []) or []
    except Exception:
        return []


def check_book_cases(prep_root: Path, src_dir: Path | None = None, res: CheckResult | None = None) -> CheckResult:
    """书内案例完整性：按 case_inventory.yaml 逐案例核对产出中是否保留。

    扫描 kb_case/handout（教材块）+ kb_case/case；任一关键词命中即算保留。
    未命中案例输出清单（含 OCR 容错变体）。
    """
    if res is None:
        res = CheckResult()
    inventory = load_case_inventory()
    if not inventory:
        res.fail("case_inventory.yaml 为空或缺失，书内案例核对跳过")
        return res

    # 收集产出全部文本（kb_case + kb_rule 下所有 md，含源文件子目录）
    contents = []
    for md in prep_root.rglob("*.md"):
        if md.name == "dify_config.md":
            continue
        contents.append(md.read_text(encoding="utf-8", errors="ignore"))
    blob = "\n".join(contents)

    missing: list[str] = []
    for item in inventory:
        keys = item.get("keys") or []
        if not keys:
            continue
        hit = any(k in blob for k in keys if k)
        if hit:
            continue
        missing.append(item.get("title_zh", str(keys)[:20]))

    total = sum(1 for i in inventory if i.get("keys"))
    hit_count = total - len(missing)
    res.ok(f"书内案例核对 {hit_count}/{total} 命中")
    if missing:
        res.fail(f"书内案例未命中 {len(missing)} 条: {missing[:6]}")
    return res


@dataclass
class CheckResult:
    passed: int = 0
    failed: int = 0
    issues: list[str] = field(default_factory=list)

    def ok(self, msg: str):
        self.passed += 1

    def fail(self, msg: str):
        self.failed += 1
        self.issues.append(msg)


_HTML_RE = re.compile(r"<[a-zA-Z/][^>]*>")
_ANCHOR_RE = re.compile(r"\]\(#")
_IMAGE_RE = re.compile(r"!\[.*?\]\(.*?\)")
_META_KEYS = ("【类型】", "【障碍类别】", "【主要行为】", "【干预目标】", "【对应工具】")


def check_structure(prep_root: Path, res: CheckResult) -> None:
    """目录结构与文件数检查（方案 B：双库 + 源文件子目录）。"""
    # 外层双库
    for kb in ("kb_case", "kb_rule"):
        if (prep_root / kb).is_dir():
            res.ok(f"双库目录存在: {kb}")
        else:
            res.fail(f"缺少双库目录: {kb}")
    # 源文件子目录（kb_case/kb_rule 下应有非空子目录）
    src_subdirs = [
        p for kb in ("kb_case", "kb_rule")
        for p in (prep_root / kb).glob("*") if p.is_dir()
    ]
    if src_subdirs:
        res.ok(f"源文件子目录 {len(src_subdirs)} 个（按原文档分目录）")
    else:
        res.fail("缺少源文件子目录")
    if (prep_root / "dify_config.md").exists():
        res.ok("dify_config.md 存在")
    else:
        res.fail("缺少 dify_config.md")
    if (prep_root / "prep_report.json").exists():
        res.ok("prep_report.json 存在")
    else:
        res.fail("缺少 prep_report.json")


def check_filenames(prep_root: Path, res: CheckResult) -> None:
    """文件名模板检查：{类型}_{...}.md，无非法字符。"""
    bad = []
    for md in prep_root.rglob("*.md"):
        if md.name == "dify_config.md":
            continue
        if re.search(r'[\\/:*?"<>|]', md.name):
            bad.append(md.name)
    if bad:
        res.fail(f"非法字符文件名 {len(bad)} 个: {bad[:5]}")
    else:
        res.ok("文件名无非法字符")


def check_content_cleanliness(prep_root: Path, res: CheckResult) -> None:
    """内容检查：无 HTML/锚点/图片残留、元数据头齐全。"""
    html_files, anchor_files, img_files = [], [], []
    meta_missing = 0
    total = 0
    for md in prep_root.rglob("*.md"):
        if md.name == "dify_config.md":
            continue
        total += 1
        content = md.read_text(encoding="utf-8")
        if _HTML_RE.search(content):
            html_files.append(md.name)
        if _ANCHOR_RE.search(content):
            anchor_files.append(md.name)
        if _IMAGE_RE.search(content):
            img_files.append(md.name)
        head = content[:200]
        if not all(k in head for k in _META_KEYS):
            meta_missing += 1
    if html_files:
        res.fail(f"HTML 残留 {len(html_files)}: {html_files[:3]}")
    else:
        res.ok("无 HTML 残留")
    if anchor_files:
        res.fail(f"锚点残留 {len(anchor_files)}: {anchor_files[:3]}")
    else:
        res.ok("无锚点残留")
    if img_files:
        res.fail(f"图片引用残留 {len(img_files)}: {img_files[:3]}")
    else:
        res.ok("无图片引用残留")
    if meta_missing:
        res.fail(f"元数据头缺失 {meta_missing}/{total}")
    else:
        res.ok(f"元数据头齐全 ({total} 文件)")


def check_anonymization(prep_root: Path, res: CheckResult) -> None:
    """脱敏检查：正文与文件名不含真实名（对照映射表）。"""
    mapping = load_anonymize_map()
    if not mapping:
        res.fail("anonymize_map 为空，脱敏未配置")
        return
    leaks = []
    for md in prep_root.rglob("*.md"):
        if md.name == "dify_config.md":
            continue
        content = md.read_text(encoding="utf-8")
        for real in mapping:
            if real and real in content:
                leaks.append(f"{md.name}:{real}")
    if leaks:
        res.fail(f"脱敏泄漏 {len(leaks)}: {leaks[:6]}")
    else:
        res.ok(f"无真实名泄漏（对照 {len(mapping)} 条映射）")


def check_case_integrity(prep_root: Path, src_dir: Path | None = None, res: CheckResult | None = None) -> CheckResult:
    """案例完整性：原始文档可识别案例数 vs 产出案例数（用户新增验收维度）。

    需要 src_dir（原始 markdown）才能计算源基准；缺省仅报产出数。
    """
    if res is None:
        res = CheckResult()
    # 评估文件在 kb_case/<源文档>/ 下（方案 B），递归查找评估_* 文件
    eval_out = [
        f.name for f in prep_root.rglob("*.md")
        if f.name.startswith("评估_") and "kb_case" in f.parts
    ]
    res.ok(f"产出评估文件 {len(eval_out)} 个")
    if src_dir:
        src = src_dir / "00评估个案汇总.md"
        if src.exists():
            import re as _re

            content = src.read_text(encoding="utf-8")
            src_reports = _re.findall(r"^#{1,2}[ \t]*([^\n]*评估报告[^\n]*)", content, _re.M)
            res.ok(f"源评估报告 {len(src_reports)} 个")
            if len(src_reports) == len(eval_out):
                res.ok("案例数量一致（源输出评估数 = 产出评估数）")
            else:
                res.fail(f"案例数量不一致：源 {len(src_reports)} vs 产出 {len(eval_out)}")
    return res


def run_all_checks(prep_root: Path, src_dir: Path | None = None) -> CheckResult:
    """运行全部验收检查。"""
    res = CheckResult()
    try:
        check_structure(prep_root, res)
        check_filenames(prep_root, res)
        check_content_cleanliness(prep_root, res)
        check_anonymization(prep_root, res)
        check_case_integrity(prep_root, src_dir, res)
        check_book_cases(prep_root, src_dir, res)
    except Exception as e:
        res.fail(f"验收过程异常: {e}")
    return res