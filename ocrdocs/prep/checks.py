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
    """目录结构与文件数检查。"""
    expect_dirs = ["kb_case", "kb_case/case", "kb_case/assessment", "kb_case/handout", "kb_rule"]
    for d in expect_dirs:
        if (prep_root / d).is_dir():
            res.ok(f"目录存在: {d}")
        else:
            res.fail(f"缺少目录: {d}")
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


def run_all_checks(prep_root: Path) -> CheckResult:
    """运行全部验收检查。"""
    res = CheckResult()
    try:
        check_structure(prep_root, res)
        check_filenames(prep_root, res)
        check_content_cleanliness(prep_root, res)
        check_anonymization(prep_root, res)
    except Exception as e:
        res.fail(f"验收过程异常: {e}")
    return res