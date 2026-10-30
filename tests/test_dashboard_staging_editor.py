"""The Dashboard staging editor writes only its scene block back to Markdown."""

from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path

from tests.test_dashboard_server import create_server, make_creator_project
from tests.test_dashboard_staging_view import BOARD, VISUAL


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "staging_editor_dashboard",
    ROOT / "skills/short-drama/scripts/dashboard_server.py",
)
assert SPEC and SPEC.loader
dashboard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dashboard)


def structured_project(root: Path) -> None:
    make_creator_project(root)
    episode = root / "剧集/EP001"
    (episode / "视觉设定.md").write_text(VISUAL, encoding="utf-8")
    (episode / "分镜.md").write_text(BOARD, encoding="utf-8")


class DashboardStagingEditorTests(unittest.TestCase):
    def store(self, workspace: Path):
        tool = dashboard.load_project_tool(ROOT / "skills/short-drama")
        return dashboard.ProjectStore(workspace, tool)

    def payload(self, project: Path, *, along: float = 0.42) -> dict[str, object]:
        storyboard = project / "剧集/EP001/分镜.md"
        positions = [
            {
                "name": "许棠",
                "present": True,
                "item": "ITEM-DESK",
                "side": "west",
                "along": along,
                "posture": "stand",
                "facing": "east",
            },
            {
                "name": "赵经理",
                "present": True,
                "item": "ITEM-CHAIR",
                "side": "on",
                "along": 0.5,
                "posture": "sit",
                "facing": "west",
            },
            {"name": "林秘书", "present": False},
        ]
        return {
            "scene": "EP001-SC001",
            "expectedVersion": hashlib.sha256(storyboard.read_bytes()).hexdigest(),
            "positions": positions,
            "extras": 4,
            "extrasWhere": "门口两侧",
        }

    def test_store_writes_scene_block_with_version_and_preserves_shots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "creator"
            structured_project(project)
            store = self.store(workspace)
            self.addCleanup(store.close)
            projects, _ = store.discover()
            stale = self.payload(project)
            result = store.update_staging(
                projects[0]["id"], "EP001", stale
            )
            self.assertTrue(result["saved"])
            storyboard = (project / "剧集/EP001/分镜.md").read_text(encoding="utf-8")
            self.assertIn("沿线：0.42", storyboard)
            self.assertIn("- 群演：4｜门口两侧", storyboard)
            self.assertIn("## SHOT-EP001-001 · 摊牌", storyboard)
            episode = store.episode(projects[0]["id"], "EP001")
            self.assertEqual(episode["board"]["blocking"][0]["extras"], 4)
            with self.assertRaises(dashboard.DashboardError) as raised:
                store.update_staging(
                    projects[0]["id"],
                    "EP001",
                    {**stale, "positions": self.payload(project, along=0.5)["positions"]},
                )
            self.assertEqual(raised.exception.status, 409)

    def test_http_action_saves_and_returns_the_repainted_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "creator"
            structured_project(project)
            server = create_server(workspace, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(thread.join, 3)
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            host, port = server.server_address[:2]
            projects = json.loads(
                self.request(
                    server,
                    host,
                    port,
                    "GET",
                    "/api/projects",
                )[2]
            )["projects"]
            body = json.dumps(self.payload(project), ensure_ascii=False).encode("utf-8")
            status, _, raw = self.request(
                server,
                host,
                port,
                "POST",
                f"/api/staging?project={projects[0]['id']}&ep=EP001",
                body,
            )
            self.assertEqual(status, 200, raw)
            result = json.loads(raw)
            self.assertTrue(result["saved"])
            self.assertEqual(result["block"]["extras"], 4)
            self.assertEqual(result["block"]["positions"][0]["along"], "0.42")

    @staticmethod
    def request(server, host, port, method: str, path: str, body: bytes | None = None):
        connection = http.client.HTTPConnection(host, port, timeout=5)
        headers = {
            "Host": f"{host}:{port}",
            "X-Short-Drama-Token": server.access_token,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        status = response.status
        connection.close()
        return status, dict(response.getheaders()), raw


if __name__ == "__main__":
    unittest.main()
