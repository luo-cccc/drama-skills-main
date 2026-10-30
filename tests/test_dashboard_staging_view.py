"""The Dashboard turns structured staging into drawable scene plans."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "dashboard_staging_views",
    ROOT / "skills/short-drama/scripts/creator_views.py",
)
assert SPEC and SPEC.loader
views = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(views)


VISUAL = """\
# EP001 视觉设定

## 地点 · 旧办公室
- 识别锚点：中央办公桌、背墙书柜。

### 空间视图 · VIEW-EP001-OFFICE-MAIN · 主视角
- 图片：REF-OFFICE（顺序：1）· 剧集/EP001/制作成果/images/office.png《办公室场景板》
- 认图来源：picture
- 屏幕方向：机位在南侧向北看，画面左为西、右为东
- 平面物件：ITEM-DESK《办公桌》（图框：0.20, 0.44, 0.80, 0.72；平面：0.22, 0.38, 0.78, 0.64；可坐：否；圆：否）
- 平面物件：ITEM-CHAIR《旧椅子》（图框：0.58, 0.18, 0.78, 0.42；平面：0.60, 0.08, 0.82, 0.30；可坐：是；圆：否）
"""


BOARD = """\
# EP001 分镜

## 场景站位 · EP001-SC001 · 旧办公室
- 空间视图：VIEW-EP001-OFFICE-MAIN
- 固定锚点：办公桌在房间中央。
- 人物位置：许棠｜物：ITEM-DESK｜侧：west｜沿线：0.60｜姿态：stand｜朝向：east
- 人物位置：赵经理｜物：ITEM-CHAIR｜侧：on｜沿线：0.50｜姿态：sit｜朝向：west
- 人物位置：林秘书｜在场：否
- 群演：2｜门口两侧

## SHOT-EP001-001 · 摊牌
- 来源：EP001-SC001
- 时长：2s
- 景别/机位：双人中景，平视
- 运镜：固定；两人都在画内。
- 起点：两人隔桌相对。
- 唯一动作：许棠把文件推到桌上。
- 终点：文件停在桌面。
- 图片提示词项：无
- 输入参考图：无（创作者已明确选择文生视频）。
- 视觉依据：无

### 冻结关键帧提示词
> two people face each other.
"""


class DashboardStagingViewTests(unittest.TestCase):
    def test_space_views_expose_plan_items_and_scene_image(self) -> None:
        parsed = views.parse_space_views(VISUAL)
        self.assertEqual(len(parsed), 1)
        view = parsed[0]
        self.assertEqual(view["location"], "旧办公室")
        self.assertEqual(view["image"], "剧集/EP001/制作成果/images/office.png")
        self.assertEqual([item["id"] for item in view["items"]], ["ITEM-DESK", "ITEM-CHAIR"])
        self.assertTrue(view["items"][1]["seat"])

    def test_scene_positions_get_top_view_points(self) -> None:
        space_views = views.parse_space_views(VISUAL)
        blocks = views.parse_scene_blocking(
            BOARD.split("\n## SHOT-", 1)[0], space_views
        )
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertEqual(block["view"]["id"], "VIEW-EP001-OFFICE-MAIN")
        self.assertEqual(block["extras"], 2)
        present = {
            person["name"]: person for person in block["positions"] if person["present"]
        }
        self.assertEqual(set(present), {"许棠", "赵经理"})
        self.assertEqual(present["许棠"]["posture"], "stand")
        self.assertIsNotNone(present["许棠"]["point"])
        self.assertIsNotNone(present["赵经理"]["point"])
        absent = next(person for person in block["positions"] if person["name"] == "林秘书")
        self.assertFalse(absent["present"])
        self.assertIsNone(absent["point"])

    def test_storyboard_parser_keeps_legacy_rows_and_adds_the_plan(self) -> None:
        parsed = views.parse_storyboard(BOARD, views.parse_space_views(VISUAL))
        block = parsed["blocking"][0]
        self.assertTrue(block["rows"])
        self.assertEqual(block["view"]["screenDirection"], "机位在南侧向北看，画面左为西、右为东")
        self.assertEqual(parsed["shots"][0]["id"], "SHOT-EP001-001")

    def test_crlf_documents_keep_the_plan_and_positions(self) -> None:
        parsed = views.read_episode(
            "EP001",
            {
                views.SCREENPLAY: "# EP001 剧本\r\n",
                views.SETTINGS: VISUAL.replace("\n", "\r\n"),
                views.STORYBOARD: BOARD.replace("\n", "\r\n"),
                views.IMAGE_PROMPTS: None,
                views.VIDEO_PROMPTS: None,
            },
            None,
        )
        block = parsed["board"]["blocking"][0]
        self.assertEqual(len(block["view"]["items"]), 2)
        self.assertEqual(len(block["positions"]), 3)

    def test_prose_only_staging_still_has_no_plan(self) -> None:
        board = BOARD.replace(
            "- 空间视图：VIEW-EP001-OFFICE-MAIN\n", ""
        ).replace(
            "- 人物位置：许棠｜物：ITEM-DESK｜侧：west｜沿线：0.60｜姿态：stand｜朝向：east\n",
            "",
        ).replace(
            "- 人物位置：赵经理｜物：ITEM-CHAIR｜侧：on｜沿线：0.50｜姿态：sit｜朝向：west\n",
            "",
        )
        parsed = views.parse_storyboard(board, views.parse_space_views(VISUAL))
        self.assertIsNone(parsed["blocking"][0]["view"])
        self.assertEqual(parsed["blocking"][0]["positions"], [])

    def test_render_scene_block_replaces_only_editable_staging_lines(self) -> None:
        block = views.parse_scene_blocking(
            BOARD.split("\n## SHOT-", 1)[0], views.parse_space_views(VISUAL)
        )[0]
        positions = [dict(position) for position in block["positions"]]
        positions[0]["side"] = "east"
        positions[0]["along"] = 0.25
        rendered = views.render_scene_block(
            BOARD,
            "EP001-SC001",
            positions,
            3,
            "窗边",
        )
        self.assertIn("- 固定锚点：办公桌在房间中央。", rendered)
        self.assertIn(
            "- 人物位置：许棠｜物：ITEM-DESK｜侧：east｜沿线：0.25"
            "｜姿态：stand｜朝向：east",
            rendered,
        )
        self.assertIn("- 群演：3｜窗边", rendered)
        self.assertIn("## SHOT-EP001-001 · 摊牌", rendered)
        parsed = views.parse_storyboard(rendered, views.parse_space_views(VISUAL))
        self.assertEqual(parsed["blocking"][0]["extras"], 3)
        self.assertEqual(parsed["blocking"][0]["positions"][0]["along"], "0.25")

    def test_render_scene_block_keeps_crlf(self) -> None:
        board = BOARD.replace("\n", "\r\n")
        block = views.parse_scene_blocking(
            board.split("\r\n## SHOT-", 1)[0], views.parse_space_views(VISUAL)
        )[0]
        rendered = views.render_scene_block(
            board,
            block["scene"],
            [dict(position) for position in block["positions"]],
            block["extras"],
            block["extrasWhere"],
        )
        self.assertIn("\r\n", rendered)
        self.assertNotIn("\n", rendered.replace("\r\n", ""))


if __name__ == "__main__":
    unittest.main()
