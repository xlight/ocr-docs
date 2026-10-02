"""案例文档 → Dify 知识库预处理（`ocr-docs prep` 子命令）。

将案例目录下的 Markdown（评估报告/个案记录/教学案例/讲义/教材/映射规则）转为
适合 Dify 知识库检索的结构化文档集：清洗噪声 → 语义拆分 → 元数据注入 →
脱敏 → 按双库（案例库/映射规则库）输出。

模块划分：
- clean.py     清洗（锚点/表格/标点/错填/图片）
- split.py     文档类型检测与语义拆分
- metadata.py  元数据提取/注入 + 文件名生成
- anonymize.py 脱敏
- output.py    双库输出 + 质量自检
"""

from ocrdocs.prep.pipeline import run_prep

__all__ = ["run_prep"]