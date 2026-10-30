"""Reference-only workspaces and anchor-before-derived production jobs."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SUITE = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, SUITE / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    SERVER_MODULES[name] = module
    spec.loader.exec_module(module)
    return module


SERVER_MODULES: dict[str, object] = {}


project_tool = load_module(
    "reference_project_tool", "skills/short-drama/scripts/project_tool.py"
)
production_tool = load_module(
    "reference_production_tool",
    "skills/short-drama-produce/scripts/production_tool.py",
)


class ReferenceImageWorkflowTests(unittest.TestCase):
    def make_workspace(self, directory: str) -> Path:
        root = Path(directory) / "reference"
        project_tool.initialize_project(
            root,
            title="角色参考图",
            language="zh-CN",
            prompt_language="en",
            aspect_ratio="2:3",
            mode="reference-only",
            suite_root=SUITE / "skills/short-drama",
        )
        return root

    def adapter_config(self, root: Path) -> Path:
        path = root.parent / "adapters.json"
        path.write_text(
            json.dumps(
                {
                    "adapters": {
                        "fixture": {
                            "command": [
                                sys.executable,
                                str(
                                    SUITE
                                    / "skills/short-drama-produce/scripts/fixture_adapter.py"
                                ),
                            ],
                            "timeout_seconds": 30,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        return path

    def write_prompts(self, root: Path, anchor_path: str = "") -> None:
        reference = (
            "无外部参考"
            if not anchor_path
            else (
                "REF-HERO-ANCHOR（顺序：1）· "
                f"{anchor_path}《角色锚点》"
                "（控制：身份、造型；不得控制：表情、构图）"
            )
        )
        (root / "参考图提示词.md").write_text(
            "# 参考图提示词\n\n"
            "## IMG-HERO-ANCHOR · 角色正面全身锚点\n\n"
            "- 参考：无外部参考\n\n"
            "### 可复制提示词\n"
            "> A young East Asian woman in a plain grey coat, full body, "
            "neutral expression, clean white background.\n\n"
            "## IMG-HERO-FACE · 角色正脸\n\n"
            f"- 参考：{reference}\n\n"
            "### 可复制提示词\n"
            "> The same young East Asian woman, front head-and-shoulders portrait, "
            "neutral expression, clean white background.\n",
            encoding="utf-8",
        )

    def job(
        self,
        *,
        job_id: str,
        entry: str,
        prompt: str,
        output: str,
        stage: str,
        group: str = "HERO",
        view: str = "front-full",
        parent: str | None = None,
        parent_output: dict[str, str] | None = None,
        bindings: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        document: dict[str, object] = {
            "schema_version": "1.0",
            "job_id": job_id,
            "modality": "image",
            "adapter": "fixture",
            "prompt": prompt,
            "source": "参考图提示词.md",
            "source_entry": entry,
            "outputs": [output],
            "parameters": {},
            "overwrite": False,
            "production_profile": "reference-sheet",
            "reference_stage": stage,
            "reference_group": group,
            "reference_view": view,
            "depends_on_job_id": parent,
            "depends_on_output": parent_output,
        }
        if bindings:
            document["references"] = [binding["path"] for binding in bindings]
            document["reference_bindings"] = bindings
        return document

    def write_job(self, root: Path, document: dict[str, object]) -> Path:
        path = root.parent / f"{document['job_id']}.json"
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return path

    def anchor_job(self) -> dict[str, object]:
        return self.job(
            job_id="REF-HERO-ANCHOR-JOB",
            entry="IMG-HERO-ANCHOR",
            prompt=(
                "A young East Asian woman in a plain grey coat, full body, "
                "neutral expression, clean white background."
            ),
            output="production/reference/HERO/front-full.v1.png",
            stage="anchor",
            view="front-full",
        )

    def derived_job(self, anchor_digest: str) -> dict[str, object]:
        anchor_path = "production/reference/HERO/front-full.v1.png"
        return self.job(
            job_id="REF-HERO-FACE-JOB",
            entry="IMG-HERO-FACE",
            prompt=(
                "The same young East Asian woman, front head-and-shoulders portrait, "
                "neutral expression, clean white background."
            ),
            output="production/reference/HERO/face-front.v1.png",
            stage="derived",
            view="face-front",
            parent="REF-HERO-ANCHOR-JOB",
            parent_output={"path": anchor_path, "sha256": anchor_digest},
            bindings=[
                {
                    "slot_id": "REF-HERO-ANCHOR",
                    "order": 1,
                    "path": anchor_path,
                    "label": "角色锚点",
                    "role": "identity_and_look",
                    "may_control": ["身份", "造型"],
                    "must_not_control": ["表情", "构图"],
                }
            ],
        )

    def test_reference_only_workspace_does_not_create_episode_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_workspace(directory)
            project = json.loads((root / "short-drama.json").read_text(encoding="utf-8"))
            self.assertEqual(project["project_mode"], "reference-only")
            self.assertTrue((root / "参考图提示词.md").is_file())
            self.assertFalse((root / "剧集").exists())
            self.assertEqual(
                project_tool.project_status(root)["project_mode"], "reference-only"
            )

    def test_derived_view_cannot_prepare_before_anchor_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_workspace(directory)
            self.write_prompts(
                root, "production/reference/HERO/front-full.v1.png"
            )
            anchor_job = self.write_job(root, self.anchor_job())
            production_tool.prepare_job(root, anchor_job)
            derived_job = self.write_job(root, self.derived_job("0" * 64))
            with self.assertRaisesRegex(ValueError, "no current successful output"):
                production_tool.prepare_job(root, derived_job)

    def test_anchor_then_derived_runs_and_parent_change_requires_reconfirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_workspace(directory)
            self.write_prompts(root)
            config = self.adapter_config(root)
            anchor_job = self.write_job(root, self.anchor_job())
            anchor_preview = production_tool.prepare_job(root, anchor_job)
            production_tool.confirm_job(
                root,
                job_id=anchor_preview["job_id"],
                confirmation=anchor_preview["confirmation"],
            )
            production_tool.run_job(
                root,
                job_id=anchor_preview["job_id"],
                adapter_config=config,
            )
            anchor = root / "production/reference/HERO/front-full.v1.png"
            digest = hashlib.sha256(anchor.read_bytes()).hexdigest()
            self.write_prompts(root, "production/reference/HERO/front-full.v1.png")
            derived_job = self.write_job(root, self.derived_job(digest))
            derived_preview = production_tool.prepare_job(root, derived_job)
            production_tool.confirm_job(
                root,
                job_id=derived_preview["job_id"],
                confirmation=derived_preview["confirmation"],
            )
            production_tool.run_job(
                root,
                job_id=derived_preview["job_id"],
                adapter_config=config,
            )
            self.assertTrue((root / "production/reference/HERO/face-front.v1.png").is_file())
            manifest = json.loads(
                (root / "production/reference/index.json").read_text(encoding="utf-8")
            )
            views = manifest["groups"]["HERO"]["views"]
            self.assertEqual(views["front-full"]["current"]["version"], 1)
            self.assertIsNone(views["front-full"]["current"]["depends_on_job_id"])
            self.assertEqual(
                views["face-front"]["current"]["depends_on_job_id"],
                "REF-HERO-ANCHOR-JOB",
            )

            # A parent output changed outside the tool; the derived result can no
            # longer claim its recorded lineage.
            anchor.write_bytes(b"changed anchor")
            status = production_tool.job_status(root, job_id="REF-HERO-FACE-JOB")
            self.assertEqual(status["state"], "needs_reconfirmation")

    def test_changed_anchor_after_confirmation_blocks_derived_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_workspace(directory)
            self.write_prompts(root)
            config = self.adapter_config(root)
            anchor_job = self.write_job(root, self.anchor_job())
            anchor_preview = production_tool.prepare_job(root, anchor_job)
            production_tool.confirm_job(
                root,
                job_id=anchor_preview["job_id"],
                confirmation=anchor_preview["confirmation"],
            )
            production_tool.run_job(
                root,
                job_id=anchor_preview["job_id"],
                adapter_config=config,
            )
            anchor = root / "production/reference/HERO/front-full.v1.png"
            digest = hashlib.sha256(anchor.read_bytes()).hexdigest()
            self.write_prompts(root, "production/reference/HERO/front-full.v1.png")
            derived_job = self.write_job(root, self.derived_job(digest))
            preview = production_tool.prepare_job(root, derived_job)
            production_tool.confirm_job(
                root,
                job_id=preview["job_id"],
                confirmation=preview["confirmation"],
            )
            anchor.write_bytes(b"changed after confirmation")
            with self.assertRaisesRegex(ValueError, "parent output changed"):
                production_tool.run_job(
                    root,
                    job_id=preview["job_id"],
                    adapter_config=config,
                )
            self.assertFalse(
                (root / "production/reference/HERO/face-front.v1.png").exists()
            )


if __name__ == "__main__":
    unittest.main()
