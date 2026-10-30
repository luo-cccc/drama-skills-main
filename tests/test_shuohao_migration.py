"""The shipped Shuohao example migrates into a usable Drama project."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHUOHAO = ROOT.parent / "shuohao-skills-main"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MIGRATION = load_module("shuohao_migration", ROOT / "tools/migrate_shuohao.py")
CHECK = load_module(
    "migration_creator_check",
    ROOT / "skills/short-drama/scripts/creator_markdown_check.py",
)
VIEWS = load_module(
    "migration_creator_views",
    ROOT / "skills/short-drama/scripts/creator_views.py",
)


@unittest.skipUnless(SHUOHAO.is_dir(), "Shuohao source snapshot is unavailable")
class ShuohaoMigrationTests(unittest.TestCase):
    def migrate(self, directory: str, *, frames_root: Path | None = None) -> Path:
        destination = Path(directory) / "migrated"
        MIGRATION.migrate(
            source_root=SHUOHAO,
            destination=destination,
            frames_root=frames_root,
        )
        return destination

    def test_real_project_migrates_to_creator_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.migrate(directory)
            episode = project / "剧集/EP001"
            for name in ("剧本.md", "视觉设定.md", "图片提示词.md", "分镜.md", "视频提示词.md"):
                self.assertTrue((episode / name).is_file(), name)
            self.assertTrue((project / "项目开发/改编大纲.md").is_file())
            self.assertTrue((project / "项目开发/迁移待决.md").is_file())
            visual = (episode / "视觉设定.md").read_text(encoding="utf-8")
            board = (episode / "分镜.md").read_text(encoding="utf-8")
            video = (episode / "视频提示词.md").read_text(encoding="utf-8")
            self.assertIn("### 空间视图 · VIEW-S02-MAIN", visual)
            self.assertIn("- 人物位置：", board)
            self.assertIn("PLAN-START", board)
            self.assertIn("## GROUP-EP001-01", video)

    def test_migrated_episode_is_read_by_checker_and_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.migrate(directory)
            episode = project / "剧集/EP001"
            errors = CHECK.validate_episode(episode, project)
            self.assertEqual(errors, [])
            texts = {
                name: (episode / name).read_text(encoding="utf-8")
                for name in CHECK.REQUIRED_DOCUMENTS
            }
            parsed = VIEWS.read_episode("EP001", texts, None)
            self.assertEqual(parsed["problems"], [])
            block = parsed["board"]["blocking"][0]
            self.assertIsNotNone(block["view"])
            self.assertTrue(any(person["point"] for person in block["positions"]))
            self.assertGreater(len(parsed["board"]["shots"]), 20)
            self.assertEqual(len(parsed["videoGroups"]), 10)

    def test_destination_must_be_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "migrated"
            destination.mkdir()
            (destination / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(MIGRATION.MigrationError, "absent or empty"):
                MIGRATION.migrate(
                    source_root=SHUOHAO,
                    destination=destination,
                )
            self.assertEqual((destination / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_available_storyboard_frames_are_bound_as_real_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            frames = Path(directory) / "frames/E01-01"
            frames.mkdir(parents=True)
            for number in range(1, 5):
                (frames / f"f{number}.png").write_bytes(f"frame-{number}".encode())
            project = self.migrate(directory, frames_root=frames.parent)
            episode = project / "剧集/EP001"
            board = (episode / "分镜.md").read_text(encoding="utf-8")
            self.assertIn("REF-START（顺序：1）", board)
            self.assertTrue(
                (episode / "制作成果/images/E01-01-f1.png").is_file()
            )


if __name__ == "__main__":
    unittest.main()
