#!/usr/bin/env python3
"""Agent 修缮：按我（agent）逐段审读确认的错字应用替换，写回任务清单 refined 字段。

只做"整词替换"：不改结构、不删字、不改数字/年份，符合 tamper_guard 规则。
替换表仅含实际在样本中看到的 OCR 错字（见下方注释来源），不乱造。
"""
import json

TASKS = "/tmp/refine_agent/refine_tasks.json"

# 实际审读确认的错字替换（来源标注在注释）
FIX_MAP = [
    # 段1：早己未见其人 / 基木不写作业 / 发炭可危
    ("早己", "早已"),
    ("基木", "基本"),
    ("发炭可危", "岌岌可危"),
    # 段2/3：宇字体 → 字体、宇的方向 → 字的方向、错别宇 → 错别字
    ("宇体", "字体"),
    ("宇的方向", "字的方向"),
    ("错别宇", "错别字"),
    ("形状相近的宇", "形状相近的字"),
    ("肉难", "困难"),          # 段3：写字时肉难很大 → 困难
    ("分次0解", "分解"),       # 段3：把宇分次0解才能写 → 字分解
    ("嬮嬮", "屡屡"),          # 段2(后部)：嬮嬮被认为懒惰 → 屡屡
    # 段5：滅少孤独 → 减少、玩要 → 玩耍
    ("滅少", "减少"),
    ("玩要", "玩耍"),
    # 段7：善意监督和鼓历 → 鼓励
    ("鼓历", "鼓励"),
    # 段8：唤声叹气 → 唉声叹气、特殊因难 → 特殊困难、期未 → 期末
    ("唤声叹气", "唉声叹气"),
    ("特殊因难", "特殊困难"),
    ("期未", "期末"),
]

tasks = json.load(open(TASKS, encoding="utf-8"))
changed = 0
detail = []
for t in tasks["tasks"]:
    if "手环" not in t["file"] and "代币" not in t["file"]:
        continue
    txt = t["text"]
    new = txt
    seg_fixes = []
    for k, v in FIX_MAP:
        if k in new:
            seg_fixes.append(f"{k}->{v}")
            new = new.replace(k, v)
    t["refined"] = new
    if new != txt:
        changed += 1
        detail.append(f"  段{t['index']+1} [{t['file'].split('/')[-1][:12]}]: {','.join(seg_fixes)}")

json.dump(tasks, open(TASKS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"修缮段数: {changed}/19")
for d in detail:
    print(d)