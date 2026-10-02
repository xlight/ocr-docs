"""最终验证：源评估报告 vs 产出评估文件一一对应。"""
import glob
import os
import re

SRC = "/Users/xlight/IdeaProjects/国特/京小融/案例/markdown/00评估个案汇总.md"
OUT = "/tmp/prep_out6"

content = open(SRC, encoding="utf-8").read()
reports = [r.strip() for r in re.findall(r"^#{1,2}[ \t]*([^\n]*评估报告[^\n]*)", content, re.M)]
print(f"源评估报告: {len(reports)}")

outs = [os.path.basename(f) for f in glob.glob(f"{OUT}/kb_case/assessment/*.md")]
eval_outs = [o for o in outs if o.startswith("评估")]
print(f"产出评估文件: {len(eval_outs)}")

print("\n对应关系:")
unmatched = []
for r in reports:
    key = r.split("评估报告")[0].strip()[:10]
    ok = any(key in o for o in eval_outs)
    if not ok:
        unmatched.append(r)
    print(f"  {'✓' if ok else '❌'} {r[:40]}")

print(f"\n未对应: {len(unmatched)}")
for u in unmatched:
    print("   ", u)  # noqa