"""验证：原始文档可识别案例数 vs 产出文档案例数。"""
import glob
import os

SRC = "/Users/xlight/IdeaProjects/国特/京小融/案例/markdown"
OUT = "/tmp/prep_out5"

checks = ["当语文教师遇到阅读障碍", "朗读错误类型分析", '"小"手环', "包字族个训课",
          "分心的孩子", "一以语音意识缺陷型阅读障碍", "书写困难学生的作文教学"]

handout = glob.glob(f"{OUT}/kb_case/handout/*.md")
print("书内案例在产出教材块中的保留情况:")
for key in checks:
    hit = [os.path.basename(f)[:40] for f in handout if key in open(f, encoding="utf-8").read()]
    print(f"  {key}: {len(hit)} 处 -> {hit[:2]}")

print("\n=== 源 vs 产出 案例对比汇总 ===")
print("源可识别案例:")
print("  评估汇总: 26 个评估报告")
print("  个案记录表: 14 个")
print("  案例1和2: 2 个")
print("  案例.md(叙事): 1 篇(含多个学生)")
print("  书-遇见阅读障碍: ~9 处'案例'标题")
print("  书-与众不同的学生: 书名即'案例精选'(大量案例)")
print(f"\n产出案例:")
case = glob.glob(f"{OUT}/kb_case/case/*.md")
assess = glob.glob(f"{OUT}/kb_case/assessment/*.md")
print(f"  kb_case/case: {len(case)} 文件")
print(f"  kb_case/assessment: {len(assess)} 文件(评估+个案)")