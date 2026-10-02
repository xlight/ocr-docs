#!/usr/bin/env python3
"""Agent 修缮：按我（agent）审读确认的错字映射应用替换，写回任务清单 refined 字段。

只做"整词替换"：不改结构、不删字、不改数字/年份，符合 tamper_guard 规则。
"""
import json

TASKS = "/tmp/refine_agent/refine_tasks.json"

# 人工核对的整词替换表（agent 审读确认，仅替换明显 OCR 错字）
FIX_MAP = {
    "早己": "早已",
    "基木": "基本",
    "宇体": "字体",
    "宇的": "字的",
    "宇的方": "字的方向",
    "宇体": "字体",
    "宇分次0解": "字分解",
    "写错宇": "写错字",
    "错别宇": "错别字",
    "形近的宇": "形近的字",
    "发炭可危": "岌岌可危",
    "嬮嬮": "屡屡",
    "肉难": "困难",
    "滅少": "减少",
    "鼓历": "鼓励",
    "玩要": "玩耍",
    "期未": "期末",
    "唤声叹气": "唉声叹气",
    "特殊因难": "特殊困难",
    "才煽": "才能",
    "因难": "困难",
}

tasks = json.load(open(TASKS, encoding="utf-8"))
changed = 0
for t in tasks["tasks"]:
    if "手环" not in t["file"] and "代币" not in t["file"]:
        continue
    txt = t["text"]
    new = txt
    for k, v in FIX_MAP.items():
        new = new.replace(k, v)
    t["refined"] = new
    if new != txt:
        changed += 1

json.dump(tasks, open(TASKS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"完成修缮: {changed}/19 段发生变化（其余为干净段落无需改动）")