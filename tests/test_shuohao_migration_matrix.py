"""Synthetic migration matrix for source shapes the real snapshot does not cover."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


migration = load("migration_matrix", ROOT / "tools/migrate_shuohao.py")
check = load(
    "migration_matrix_check",
    ROOT / "skills/short-drama/scripts/creator_markdown_check.py",
)


def write_json(path: Path, document: dict[str, object], *, crlf: bool = False) -> Path:
    text = json.dumps(document, ensure_ascii=False, indent=2)
    if crlf:
        text = text.replace("\n", "\r\n")
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return path


class MigrationMatrixTests(unittest.TestCase):
    def make_full_source(self, root: Path, *, crlf: bool = False) -> dict[str, Path]:
        root.mkdir()
        outline = {
            "source": "合成迁移矩阵",
            "params": {"genre": "剧情", "episodes": 2, "minutesPerEpisode": 1},
            "characters": [
                {"id": "C01", "name": "许棠", "tier": "主角", "role": "调查者"}
            ],
            "scenes": [
                {"id": "S01", "name": "旧办公室"},
                {"id": "S02", "name": "河边"},
            ],
            "episodes": [
                {"ep": 1, "synopsis": "发现文件。"},
                {"ep": 2, "synopsis": "追到河边。"},
            ],
        }
        script = {
            "source": "合成迁移矩阵",
            "episodes": [
                {
                    "ep": 1,
                    "targetSeconds": 6,
                    "scenes": [
                        {
                            "sceneId": "S01",
                            "lighting": "日",
                            "characters": ["C01"],
                            "props": [],
                            "flow": [
                                {"action": "许棠把文件推到桌上。"},
                                {"speaker": "C01", "line": "这不是原件。"},
                            ],
                        }
                    ],
                },
                {
                    "ep": 2,
                    "scenes": [
                        {
                            "sceneId": "S02",
                            "lighting": "雨夜",
                            "characters": ["C01"],
                            "props": [],
                            "flow": [
                                {"action": "许棠沿着河岸停下。"},
                                {"speaker": "C01", "line": "脚印到这里断了。"},
                            ],
                        }
                    ],
                },
            ],
        }
        cast = {
            "source": "合成迁移矩阵",
            "characters": [
                {
                    "name": "许棠",
                    "persona": {
                        "gender": "女",
                        "ageRange": "20 多岁",
                        "identity": "调查者",
                        "appearance": "短发，灰色外套",
                    },
                    "image": {"sheet": "character sheet prompt"},
                }
            ],
        }
        art = {
            "source": "合成迁移矩阵",
            "dynasty": "当下",
            "scenes": [
                {
                    "id": "S01",
                    "name": "旧办公室",
                    "summary": "一间旧办公室",
                    "anchors": [{"name": "办公桌", "desc": "靠窗"}],
                    "lighting": [{"state": "日", "prompt": "冷白日光"}],
                    "image": {"sheet": "old office plate prompt"},
                },
                {
                    "id": "S02",
                    "name": "河边",
                    "summary": "雨夜河岸",
                    "anchors": [{"name": "护栏", "desc": "沿河"}],
                    "lighting": [{"state": "雨夜", "prompt": "路灯冷光"}],
                    "image": {"sheet": "riverside plate prompt"},
                },
            ],
            "props": [],
        }
        staging = {
            "source": "合成迁移矩阵",
            "locations": [
                {
                    "sceneId": "S01",
                    "name": "旧办公室",
                    "readFrom": "prompt",
                    "items": [
                        {"name": "办公桌", "plan": [0.2, 0.3, 0.8, 0.7], "on": False}
                    ],
                },
                {
                    "sceneId": "S02",
                    "name": "河边",
                    "readFrom": "prompt",
                    "items": [
                        {"name": "护栏", "plan": [0.3, 0.1, 0.7, 0.2], "on": False}
                    ],
                },
            ],
            "scenes": [
                {
                    "ep": 1,
                    "scene": 1,
                    "cast": [{"name": "许棠"}],
                    "places": [
                        {
                            "name": "许棠",
                            "present": True,
                            "item": "办公桌",
                            "side": "west",
                            "along": 0.5,
                            "posture": "stand",
                            "facing": "east",
                        }
                    ],
                    "extras": 0,
                },
                {
                    "ep": 2,
                    "scene": 1,
                    "cast": [{"name": "许棠"}],
                    "places": [
                        {
                            "name": "许棠",
                            "present": True,
                            "item": "护栏",
                            "side": "north",
                            "along": 0.5,
                            "posture": "stand",
                            "facing": "south",
                        }
                    ],
                    "extras": 0,
                },
            ],
        }

        def episode_board(ep: int, scene_index: int) -> dict[str, object]:
            return {
                "ep": ep,
                "segments": [
                    {
                        "id": f"E{ep:02d}-01",
                        "sceneIndex": scene_index,
                        "soundscape": "环境底噪",
                        "h3Prompt": "one continuous shot",
                        "cuts": [
                            {
                                "beats": [1, 1],
                                "seconds": 2,
                                "size": "medium",
                                "camera": "Static Shot",
                                "characters": ["C01"],
                                "props": [],
                                "frame": "许棠在场景中",
                                "shot": "她把文件推到桌上"
                                if ep == 1
                                else "她沿河岸停下",
                                "lens": "35mm",
                                "cameraPosition": "平视",
                                "stability": "stable",
                            },
                            {
                                "beats": [2, 2],
                                "seconds": 3,
                                "size": "close",
                                "camera": "Static Shot",
                                "characters": ["C01"],
                                "props": [],
                                "frame": "许棠说话",
                                "shot": "她说出关键一句",
                                "lens": "50mm",
                                "cameraPosition": "近景",
                                "stability": "stable",
                            },
                        ],
                    }
                ],
            }

        storyboard = {
            "promptLang": "en",
            "aspectRatio": "9:16",
            "episodes": [episode_board(1, 1), episode_board(2, 1)],
        }
        return {
            "outline": write_json(root / "outline.json", outline, crlf=crlf),
            "cast": write_json(root / "cast.json", cast, crlf=crlf),
            "art": write_json(root / "art.json", art, crlf=crlf),
            "script": write_json(root / "script.json", script, crlf=crlf),
            "staging": write_json(root / "staging.json", staging, crlf=crlf),
            "storyboard": write_json(
                root / "storyboard.json", storyboard, crlf=crlf
            ),
        }

    def test_two_episode_crlf_project_is_clean_and_uses_plan_without_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_full_source(root / "source", crlf=True)
            destination = root / "migrated"
            result = migration.migrate(
                source_root=root / "source",
                destination=destination,
                **source,
            )
            self.assertEqual(result["episodes"], [1, 2])
            for ep in ("EP001", "EP002"):
                episode = destination / "剧集" / ep
                for name in check.REQUIRED_DOCUMENTS:
                    self.assertTrue((episode / name).is_file(), f"{ep}/{name}")
                self.assertEqual(check.validate_episode(episode, destination), [])
            self.assertIn(
                "PLAN-START",
                (destination / "剧集/EP001/分镜.md").read_text(encoding="utf-8"),
            )

    def test_outline_only_migrates_the_development_surface_without_fake_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            outline = write_json(
                source / "outline.json",
                {
                    "source": "只有大纲",
                    "params": {"episodes": 2},
                    "episodes": [{"ep": 1}, {"ep": 2}],
                },
            )
            destination = root / "migrated"
            result = migration.migrate(
                source_root=source,
                destination=destination,
                outline=outline,
            )
            self.assertEqual(result["episodes"], [1, 2])
            self.assertTrue((destination / "项目开发/改编大纲.md").is_file())
            self.assertFalse((destination / "剧集/EP001/剧本.md").exists())
            self.assertFalse((destination / "剧集/EP001/分镜.md").exists())

    def test_script_only_migration_records_missing_upstream_instead_of_inventing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            script = write_json(
                source / "script.json",
                {
                    "source": "只有剧本",
                    "episodes": [
                        {
                            "ep": 1,
                            "scenes": [
                                {
                                    "sceneId": "S09",
                                    "lighting": "日",
                                    "flow": [
                                        {"action": "她走进空房间。"},
                                        {"speaker": "C09", "line": "有人吗？"},
                                    ],
                                }
                            ],
                        }
                    ],
                },
            )
            destination = root / "migrated"
            migration.migrate(
                source_root=source,
                destination=destination,
                script=script,
            )
            episode = destination / "剧集/EP001"
            self.assertTrue((episode / "剧本.md").is_file())
            self.assertTrue((episode / "视觉设定.md").is_file())
            self.assertTrue((episode / "图片提示词.md").is_file())
            self.assertFalse((episode / "分镜.md").exists())
            self.assertFalse((episode / "视频提示词.md").exists())
            pending = (destination / "项目开发/迁移待决.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("缺少实际分镜图时", pending)


if __name__ == "__main__":
    unittest.main()
