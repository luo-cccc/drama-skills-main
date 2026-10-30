"""Dashboard reference versions compare the manifest with current bytes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_dashboard_server import make_creator_project


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reference_versions_dashboard",
    ROOT / "skills/short-drama/scripts/dashboard_server.py",
)
assert SPEC and SPEC.loader
dashboard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dashboard)


class DashboardReferenceVersionTests(unittest.TestCase):
    def store(self, workspace: Path):
        tool = dashboard.load_project_tool(ROOT / "skills/short-drama")
        return dashboard.ProjectStore(workspace, tool)

    def setup_references(self, project: Path) -> dict[str, object]:
        episode = project / "剧集/EP001"
        source = episode / "图片提示词.md"
        anchor = episode / "制作成果/images/refs/HERO/front-full.v1.png"
        face = episode / "制作成果/images/refs/HERO/face-front.v1.png"
        anchor.parent.mkdir(parents=True)
        anchor.write_bytes(b"anchor")
        face.write_bytes(b"face")
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        anchor_hash = hashlib.sha256(anchor.read_bytes()).hexdigest()
        face_hash = hashlib.sha256(face.read_bytes()).hexdigest()
        manifest = {
            "schema_version": "1.0",
            "kind": "reference_manifest",
            "groups": {
                "HERO": {
                    "id": "HERO",
                    "views": {
                        "front-full": {
                            "current": {
                                "job_id": "REF-HERO-ANCHOR",
                                "stage": "anchor",
                                "view": "front-full",
                                "version": 1,
                                "output": "剧集/EP001/制作成果/images/refs/HERO/front-full.v1.png",
                                "sha256": anchor_hash,
                                "source": "剧集/EP001/图片提示词.md",
                                "source_entry": "IMG-HERO-ANCHOR",
                                "source_sha256": source_hash,
                                "depends_on_job_id": None,
                                "depends_on_output": None,
                                "created_at": "2026-10-30T00:00:00Z",
                            },
                            "versions": [],
                        },
                        "face-front": {
                            "current": {
                                "job_id": "REF-HERO-FACE",
                                "stage": "derived",
                                "view": "face-front",
                                "version": 1,
                                "output": "剧集/EP001/制作成果/images/refs/HERO/face-front.v1.png",
                                "sha256": face_hash,
                                "source": "剧集/EP001/图片提示词.md",
                                "source_entry": "IMG-HERO-FACE",
                                "source_sha256": source_hash,
                                "depends_on_job_id": "REF-HERO-ANCHOR",
                                "depends_on_output": {
                                    "path": "剧集/EP001/制作成果/images/refs/HERO/front-full.v1.png",
                                    "sha256": anchor_hash,
                                },
                                "created_at": "2026-10-30T00:01:00Z",
                            },
                            "versions": [],
                        },
                    },
                }
            },
        }
        manifest_path = episode / "制作成果/references/index.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {
            "source": source,
            "anchor": anchor,
            "face": face,
            "anchor_hash": anchor_hash,
        }

    def test_current_parent_and_source_are_shown_as_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "creator"
            make_creator_project(project)
            self.setup_references(project)
            store = self.store(workspace)
            self.addCleanup(store.close)
            projects, _ = store.discover()
            episode = store.episode(projects[0]["id"], "EP001")
            views = {
                view["id"]: view
                for group in episode["references"]["groups"]
                for view in group["views"]
            }
            self.assertEqual(views["front-full"]["status"], "current")
            self.assertEqual(views["face-front"]["status"], "current")
            self.assertIn(
                "剧集/EP001/制作成果/images/refs/HERO/front-full.v1.png",
                episode["media"]["referenceOutputs"],
            )

    def test_source_change_png_tamper_and_parent_update_are_expired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "creator"
            make_creator_project(project)
            paths = self.setup_references(project)
            store = self.store(workspace)
            self.addCleanup(store.close)
            projects, _ = store.discover()
            source = paths["source"]
            source.write_text(
                source.read_text(encoding="utf-8") + "\n- 结语：changed\n",
                encoding="utf-8",
            )
            episode = store.episode(projects[0]["id"], "EP001")
            views = {
                view["id"]: view
                for group in episode["references"]["groups"]
                for view in group["views"]
            }
            self.assertIn("提示词已变化", views["front-full"]["reasons"])
            self.assertEqual(views["front-full"]["status"], "expired")

            # Restore the source digest, tamper the current anchor bytes, and
            # verify that the dependent face is reported through its parent.
            anchor = paths["anchor"]
            anchor.write_bytes(b"tampered")
            episode = store.episode(projects[0]["id"], "EP001")
            anchor_view = next(
                view
                for group in episode["references"]["groups"]
                for view in group["views"]
                if view["id"] == "front-full"
            )
            self.assertIn("输出图片字节已变化", anchor_view["reasons"])

    def test_reference_only_project_exposes_its_manifest_and_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "character"
            tool = dashboard.load_project_tool(ROOT / "skills/short-drama")
            tool.initialize_project(
                project,
                title="角色参考图",
                language="zh-CN",
                prompt_language="en",
                aspect_ratio="2:3",
                mode="reference-only",
                suite_root=ROOT / "skills/short-drama",
            )
            source = project / "参考图提示词.md"
            source.write_text(
                "# 参考图提示词\n\n## IMG-HERO · 正面全身\n\n"
                "- 参考：无外部参考\n\n### 可复制提示词\n> portrait\n",
                encoding="utf-8",
            )
            output = project / "production/reference/HERO/front-full.v1.png"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"\x89PNG\r\n\x1a\nanchor")
            manifest = {
                "schema_version": "1.0",
                "kind": "reference_manifest",
                "groups": {
                    "HERO": {
                        "id": "HERO",
                        "views": {
                            "front-full": {
                                "current": {
                                    "job_id": "REF-HERO",
                                    "stage": "anchor",
                                    "view": "front-full",
                                    "version": 1,
                                    "output": str(output.relative_to(project)).replace("\\", "/"),
                                    "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                                    "source": "参考图提示词.md",
                                    "source_entry": "IMG-HERO",
                                    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                                    "depends_on_job_id": None,
                                    "depends_on_output": None,
                                    "created_at": "2026-10-30T00:00:00Z",
                                },
                                "versions": [],
                            }
                        },
                    }
                },
            }
            manifest_path = project / "production/reference/index.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )
            store = self.store(workspace)
            self.addCleanup(store.close)
            projects, _ = store.discover()
            references = store.references(projects[0]["id"])
            view = references["groups"][0]["views"][0]
            self.assertEqual(view["status"], "current")
            self.assertIn(
                "production/reference/HERO/front-full.v1.png", references["media"]
            )
            source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            references = store.references(projects[0]["id"])
            self.assertEqual(
                references["groups"][0]["views"][0]["status"], "expired"
            )
            self.assertIn(
                "提示词已变化",
                references["groups"][0]["views"][0]["reasons"],
            )


if __name__ == "__main__":
    unittest.main()
