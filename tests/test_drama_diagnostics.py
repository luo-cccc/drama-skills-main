"""Drama validation carries screenplay beats, dialogue time and asset diagnostics."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/creator-first"
SPEC = importlib.util.spec_from_file_location(
    "drama_diagnostics_check",
    ROOT / "skills/short-drama/scripts/creator_markdown_check.py",
)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


class DramaDiagnosticsTests(unittest.TestCase):
    def workspace(self, directory: str) -> tuple[Path, Path]:
        project = Path(directory) / "project"
        shutil.copytree(EXAMPLE, project)
        return project, project / "EP001"

    def test_an_uncarried_screenplay_paragraph_is_not_hidden_by_its_scene(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, episode = self.workspace(directory)
            screenplay = episode / "剧本.md"
            screenplay.write_text(
                screenplay.read_text(encoding="utf-8")
                + "\n江晨把一张没被任何镜头拍到的纸条塞进抽屉。\n",
                encoding="utf-8",
            )
            errors = check.validate_episode(episode, project)
            self.assertTrue(
                any("没有被任何镜头承载" in error and "纸条塞进抽屉" in error for error in errors),
                errors,
            )

    def test_accepted_pacing_catches_dialogue_that_does_not_fit_its_shot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, episode = self.workspace(directory)
            manifest = project / "short-drama.json"
            document = {
                "format": {
                    "pacing": {
                        "spoken_characters_per_second": 1,
                        "seconds_per_action_paragraph": 0.1,
                    }
                }
            }
            manifest.write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
            screenplay = episode / "剧本.md"
            line = "江晨：这一句话有十六个字，四秒肯定说不完。"
            screenplay.write_text(
                screenplay.read_text(encoding="utf-8").replace(
                    "## EP001-SC002", f"{line}\n\n## EP001-SC002", 1
                ),
                encoding="utf-8",
            )
            storyboard = episode / "分镜.md"
            text = storyboard.read_text(encoding="utf-8")
            text = text.replace(
                "## SHOT-EP001-002 · 四个号，四个粉\n\n"
                "- 来源：EP001-SC001「四个号，加起来四个粉吧」",
                "## SHOT-EP001-002 · 四个号，四个粉\n\n"
                "- 来源：EP001-SC001「这一句话有十六个字，四秒肯定说不完」",
                1,
            )
            storyboard.write_text(text, encoding="utf-8")
            errors = check.validate_episode(episode, project)
            self.assertTrue(
                any("对白约需" in error and "SHOT-EP001-002" in error for error in errors),
                errors,
            )

    def test_asset_diagnosis_reports_missing_anchor_without_blocking_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, episode = self.workspace(directory)
            visual = episode / "视觉设定.md"
            document = visual.read_text(encoding="utf-8")
            marker = "- 识别锚点："
            self.assertIn(marker, document)
            visual.write_text(document.replace(marker, "- 可见特征：", 1), encoding="utf-8")
            report = check.diagnose_episode(episode, project)
            self.assertTrue(
                any("没有识别锚点" in note for note in report["diagnostics"]),
                report["diagnostics"],
            )
            self.assertFalse(
                any("没有识别锚点" in error for error in report["errors"]),
                report["errors"],
            )


if __name__ == "__main__":
    unittest.main()
