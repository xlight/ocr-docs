"""人工校准：两本书案例清点（基于目录人工阅读 + 章节结构辅助）。"""
import re

SRC = "/Users/xlight/IdeaProjects/国特/京小融/案例/markdown"

print("=" * 60)
print("书1《遇见阅读障碍》案例（## 编号+案例：格式，正文确认 8 个唯一）")
c1 = open(f"{SRC}/书-遇见阅读障碍教师和家长怎么做.md", encoding="utf-8").read()
# 正文案例（去重）
cases1 = {}
for m in re.finditer(r"^\s#{2,3}\s+(\d+\s*案例[：:][^\n]{0,40})", c1, re.M):
    key = re.sub(r"^\s*", "", m.group(1).strip())
    cases1.setdefault(key, 0)
    cases1[key] += 1
print(f"正文唯一案例标题: {len(cases1)} 个")
for k in cases1:
    print(f"   {k[:50]}")

print("=" * 60)
print("书2《与众不同的学生》案例（目录人工读：部分→案例结构）")
# 打印 第一~第五部分 章节标题（用于人工核对案例边界）
c2 = open(f"{SRC}/书-与众不同的学生(1).md", encoding="utf-8").read()
parts = re.findall(r"^#\s*(第[一二三四五]部分[^\n]{0,30})", c2, re.M)
print(f"部分标题: {parts}")