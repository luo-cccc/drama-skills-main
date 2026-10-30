"""Offline production packs are derived from the two creator documents."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "storyboard_pack",
    ROOT / "skills/short-drama-storyboard/scripts/storyboard_pack.py",
)
assert SPEC and SPEC.loader
pack_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pack_tool)


STORYBOARD = """\
# EP001 分镜

## SHOT-EP001-001 · 进门
- 来源：EP001-SC001
- 时长：2s
- 输入参考图：REF-START（顺序：1）· 输入/start.png《起始帧》（用途：起始帧；控制：构图；不得控制：动作）

### 冻结关键帧提示词
> She stands at the door.

## SHOT-EP001-002 · 回头
- 来源：EP001-SC001
- 时长：2s
- 输入参考图：REF-HERO（顺序：1）· 输入/hero.png《角色图》（用途：身份；控制：脸型；不得控制：构图）

### 冻结关键帧提示词
> She turns back.
"""


VIDEO = """\
# EP001 视频提示词

## MOTION-EP001-001 · 进门
- 分镜：SHOT-EP001-001
- 时长：2s

### 可复制提示词
> She walks through the door and stops.

## MOTION-EP001-002 · 回头
- 分镜：SHOT-EP001-002
- 时长：2s

### 可复制提示词
> She turns her head toward the camera.
"""


GROUP = """\

## GROUP-EP001-01 · 进门回头
- 成员：MOTION-EP001-001、MOTION-EP001-002
- 时长：4s

### 可复制提示词
> Shot 1: she walks through the door. Shot 2: she turns back.
"""


class StoryboardPackTests(unittest.TestCase):
    def make_episode(self, directory: str, *, grouped: bool = True) -> tuple[Path, Path]:
        root = Path(directory) / "project"
        episode = root / "剧集/EP001"
        episode.mkdir(parents=True)
        (root / "输入").mkdir()
        (root / "输入/start.png").write_bytes(b"start")
        (root / "输入/hero.png").write_bytes(b"hero")
        (episode / "分镜.md").write_text(STORYBOARD, encoding="utf-8")
        video = VIDEO + (GROUP if grouped else "")
        (episode / "视频提示词.md").write_text(video, encoding="utf-8")
        return root, episode

    def test_h3_pack_uses_group_and_copies_attachments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, episode = self.make_episode(directory)
            result = pack_tool.build_pack(
                episode,
                project_root=root,
                protocol="h3",
                out=None,
            )
            destination = Path(result["out"])
            self.assertEqual(result["segments"], 1)
            self.assertTrue((destination / "E01-01/prompt.md").is_file())
            self.assertEqual(
                (destination / "E01-01/f1.png").read_bytes(), b"start"
            )
            self.assertEqual(
                (destination / "E01-01/f2.png").read_bytes(), b"hero"
            )
            prompt = (destination / "E01-01/prompt.md").read_text(encoding="utf-8")
            self.assertIn("she turns back", prompt)
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["protocol"], "h3")
            self.assertEqual(manifest["segments"][0]["members"], [
                "MOTION-EP001-001",
                "MOTION-EP001-002",
            ])

    def test_seedance_pack_uses_its_own_prompt_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, episode = self.make_episode(directory, grouped=False)
            result = pack_tool.build_pack(
                episode,
                project_root=root,
                protocol="seedance",
                out=None,
            )
            destination = Path(result["out"])
            self.assertEqual(result["segments"], 2)
            self.assertTrue((destination / "E01-01/seedance.md").is_file())
            self.assertTrue((destination / "E01-02/seedance.md").is_file())

    def test_existing_pack_can_be_rebuilt_without_leaving_a_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, episode = self.make_episode(directory)
            first = pack_tool.build_pack(
                episode, project_root=root, protocol="h3", out=None
            )
            destination = Path(first["out"])
            (destination / "stale.txt").write_text("old", encoding="utf-8")
            second = pack_tool.build_pack(
                episode, project_root=root, protocol="h3", out=destination
            )
            self.assertEqual(second["segments"], 1)
            self.assertFalse((destination / "stale.txt").exists())
            self.assertEqual(
                [path.name for path in destination.parent.glob("*")],
                ["h3"],
            )

    def test_group_duration_must_equal_its_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, episode = self.make_episode(directory)
            video = (episode / "视频提示词.md").read_text(encoding="utf-8")
            (episode / "视频提示词.md").write_text(
                video.replace("- 时长：4s", "- 时长：5s"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(pack_tool.PackError, "does not equal members"):
                pack_tool.build_pack(
                    episode,
                    project_root=root,
                    protocol="h3",
                    out=None,
                )

    def test_ungrouped_and_grouped_segments_keep_source_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, episode = self.make_episode(directory)
            video = (episode / "视频提示词.md").read_text(encoding="utf-8")
            video = video.replace(
                "- 成员：MOTION-EP001-001、MOTION-EP001-002",
                "- 成员：MOTION-EP001-002",
            ).replace("- 时长：4s", "- 时长：2s")
            (episode / "视频提示词.md").write_text(video, encoding="utf-8")
            result = pack_tool.build_pack(
                episode, project_root=root, protocol="h3", out=None
            )
            manifest = json.loads(
                (Path(result["out"]) / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [segment["source_id"] for segment in manifest["segments"]],
                ["MOTION-EP001-001", "GROUP-EP001-01"],
            )

    def test_plan_and_pending_references_are_reported_without_copying_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, episode = self.make_episode(directory, grouped=False)
            board = (episode / "分镜.md").read_text(encoding="utf-8")
            (episode / "分镜.md").write_text(
                board.replace(
                    "REF-HERO（顺序：1）· 输入/hero.png《角色图》"
                    "（用途：身份；控制：脸型；不得控制：构图）",
                    "PLAN-HERO（顺序：1）· IMG-HERO《角色图》"
                    "（用途：身份；控制：脸型；不得控制：构图）；"
                    "待补参考图：侧面图",
                ),
                encoding="utf-8",
            )
            result = pack_tool.build_pack(
                episode,
                project_root=root,
                protocol="h3",
                out=None,
            )
            manifest = json.loads(
                (Path(result["out"]) / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(result["missing"], 3)
            self.assertEqual(len(manifest["segments"][1]["missing"]), 3)


if __name__ == "__main__":
    unittest.main()
