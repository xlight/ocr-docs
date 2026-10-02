"""测试 prep pipeline 的输入收集与自嵌套排除逻辑。"""
from pathlib import Path

from ocrdocs.prep.pipeline import _collect_md_files, _is_excluded_dir


class TestIsExcludedDir:
    def test_excluded_names(self):
        assert _is_excluded_dir("prep")
        assert _is_excluded_dir("refined")
        assert _is_excluded_dir("media")
        assert _is_excluded_dir(".git")

    def test_underscore_prefix(self):
        assert _is_excluded_dir("_refine_sample")
        assert _is_excluded_dir("_refine_sample_out")

    def test_normal_dir_not_excluded(self):
        assert not _is_excluded_dir("案例")
        assert not _is_excluded_dir("F")
        assert not _is_excluded_dir("我的文档")

    def test_accepts_path_object(self):
        assert _is_excluded_dir(Path("prep"))
        assert not _is_excluded_dir(Path("案例"))


class TestCollectMdFiles:
    def test_skips_excluded_subdirs(self, tmp_path):
        # 模拟 案例/markdown 目录结构：真实输入 + 输出/辅助子目录
        (tmp_path / "F").mkdir(parents=True)
        (tmp_path / "case.md").write_text("# 案例", encoding="utf-8")
        (tmp_path / "F" / "handout.md").write_text("# 讲义", encoding="utf-8")
        # 应排除的目录
        (tmp_path / "prep" / "kb_case").mkdir(parents=True)
        (tmp_path / "prep" / "kb_case" / "x.md").write_text("x", encoding="utf-8")
        (tmp_path / "_refine_sample").mkdir()
        (tmp_path / "_refine_sample" / "s.md").write_text("s", encoding="utf-8")
        (tmp_path / "media").mkdir()
        (tmp_path / "media" / "img.md").write_text("img", encoding="utf-8")

        files = _collect_md_files(tmp_path)
        names = [f.name for f in files]
        assert sorted(names) == ["case.md", "handout.md"]

    def test_recursive_keeps_nested_sources(self, tmp_path):
        (tmp_path / "子目录" / "深层").mkdir(parents=True)
        (tmp_path / "a.md").write_text("a", encoding="utf-8")
        (tmp_path / "子目录" / "深层" / "b.md").write_text("b", encoding="utf-8")

        files = _collect_md_files(tmp_path)
        assert len(files) == 2
        assert {f.relative_to(tmp_path).as_posix() for f in files} == {"a.md", "子目录/深层/b.md"}