"""Structured scene staging remains a derived, Markdown-owned contract."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGING_SPEC = importlib.util.spec_from_file_location(
    "staging_tool",
    ROOT / "skills/short-drama-storyboard/scripts/staging_tool.py",
)
assert STAGING_SPEC and STAGING_SPEC.loader
staging = importlib.util.module_from_spec(STAGING_SPEC)
sys.modules[STAGING_SPEC.name] = staging
STAGING_SPEC.loader.exec_module(staging)

CHECK_SPEC = importlib.util.spec_from_file_location(
    "staging_markdown_check",
    ROOT / "skills/short-drama/scripts/creator_markdown_check.py",
)
assert CHECK_SPEC and CHECK_SPEC.loader
check = importlib.util.module_from_spec(CHECK_SPEC)
sys.modules[CHECK_SPEC.name] = check
CHECK_SPEC.loader.exec_module(check)


VISUAL = """\
# EP003 视觉设定

## 地点 · 财务室
- 识别锚点：中央办公桌、背墙保险柜、百叶窗。

### 空间视图 · VIEW-EP003-FINANCE-MAIN · 主视角
- 图片：REF-FINANCE（顺序：1）· 剧集/EP003/制作成果/images/finance.png《财务室场景板》
- 认图来源：picture
- 屏幕方向：机位在南侧向北看，画面左为西、右为东
- 平面物件：ITEM-DESK《办公桌》（图框：0.20, 0.44, 0.80, 0.72；平面：0.22, 0.38, 0.78, 0.64；可坐：否）
- 平面物件：ITEM-CABINET《保险柜》（图框：0.60, 0.10, 0.88, 0.38；平面：0.62, 0.04, 0.90, 0.32；可坐：否）
"""


BOARD = """\
# EP003 分镜

## 场景站位 · EP003-SC001 · 财务室
- 空间视图：VIEW-EP003-FINANCE-MAIN
- 固定锚点：办公桌在房间中央；保险柜靠背墙。
- 轴线：赵经理 ↔ 沈一舟；working side：百叶窗一侧。
- 人物位置：赵经理｜物：ITEM-DESK｜侧：east｜沿线：0.50｜姿态：sit｜朝向：west
- 人物位置：沈一舟｜物：ITEM-DESK｜侧：west｜沿线：0.50｜姿态：stand｜朝向：east
- 人物位置：林秘书｜在场：否
- 群演：2｜长桌西侧南端

## SHOT-EP003-001 · 摊牌
"""


class StagingMarkdownTests(unittest.TestCase):
    def test_valid_staging_parses_and_round_trips_position_lines(self) -> None:
        document, errors = staging.validate_documents(VISUAL, BOARD)
        self.assertEqual(errors, [])
        self.assertEqual(len(document.views), 1)
        self.assertEqual(len(document.scenes), 1)
        scene = document.scenes[0]
        self.assertEqual([position.name for position in scene.positions], ["赵经理", "沈一舟", "林秘书"])
        for position in scene.positions:
            line = staging.position_line(position)
            match = staging.PERSON_LINE_RE.fullmatch(line)
            self.assertIsNotNone(match)
            parsed = staging._parse_position(match.group(1), line=1, errors=[])
            self.assertEqual(parsed, position)

    def test_prompt_only_view_can_omit_picture_box(self) -> None:
        visual = VISUAL.replace("认图来源：picture", "认图来源：prompt").replace(
            "0.20, 0.44, 0.80, 0.72", "无"
        )
        _, errors = staging.validate_documents(visual, BOARD)
        self.assertEqual(errors, [])

    def test_picture_view_requires_a_box(self) -> None:
        visual = VISUAL.replace("0.20, 0.44, 0.80, 0.72", "无")
        _, errors = staging.validate_documents(visual, BOARD)
        self.assertTrue(any("必须写图框坐标" in error for error in errors), errors)

    def test_missing_item_is_reported(self) -> None:
        board = BOARD.replace("ITEM-DESK｜侧：east", "ITEM-MISSING｜侧：east")
        _, errors = staging.validate_documents(VISUAL, board)
        self.assertTrue(any("ITEM-MISSING" in error for error in errors), errors)

    def test_overlapping_people_on_the_same_side_are_reported(self) -> None:
        board = BOARD.replace(
            "沈一舟｜物：ITEM-DESK｜侧：west｜沿线：0.50",
            "沈一舟｜物：ITEM-DESK｜侧：east｜沿线：0.50",
        )
        _, errors = staging.validate_documents(VISUAL, board)
        self.assertTrue(any("沿线至少拉开" in error for error in errors), errors)

    def test_absent_person_must_not_keep_a_position(self) -> None:
        board = BOARD.replace(
            "- 人物位置：林秘书｜在场：否",
            "- 人物位置：林秘书｜物：ITEM-DESK｜在场：否",
        )
        _, errors = staging.validate_documents(VISUAL, board)
        self.assertTrue(any("开场不在时不能写" in error for error in errors), errors)

    def test_prose_only_staging_stays_backward_compatible(self) -> None:
        board = """\
## 场景站位 · EP003-SC001 · 财务室
- 固定锚点：办公桌在房间中央。
- 人物：赵经理坐在办公桌后；沈一舟站在桌前。
- 轴线：赵经理 ↔ 沈一舟。
"""
        document, errors = staging.validate_documents(
            "## 地点 · 财务室\n", board
        )
        self.assertEqual(errors, [])
        self.assertEqual(document.views, ())
        self.assertEqual(document.scenes[0].positions, ())

    def test_cache_is_derived_and_records_the_source_digest(self) -> None:
        document, errors = staging.validate_documents(VISUAL, BOARD)
        self.assertEqual(errors, [])
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP003"
            episode.mkdir(parents=True)
            (episode / "视觉设定.md").write_text(VISUAL, encoding="utf-8")
            (episode / "分镜.md").write_text(BOARD, encoding="utf-8")
            cache = staging.write_cache(
                episode, document, VISUAL, BOARD, project_root=project
            )
            self.assertEqual(
                cache, project / ".short-drama/staging/EP003.json"
            )
            payload = staging.json.loads(cache.read_text(encoding="utf-8"))
            self.assertEqual(payload["source_digest"], staging.source_digest(VISUAL, BOARD))
            self.assertEqual(
                staging.read_cache(
                    episode, visual=VISUAL, storyboard=BOARD, project_root=project
                )["source_digest"],
                payload["source_digest"],
            )
            self.assertIsNone(
                staging.read_cache(
                    episode,
                    visual=VISUAL,
                    storyboard=BOARD + "\n- 变化：移动。\n",
                    project_root=project,
                )
            )
            cache.unlink()
            rebuilt, rebuilt_errors, _, _ = staging.load_episode(episode)
            self.assertEqual(rebuilt_errors, [])
            self.assertEqual(rebuilt, document)

    def test_main_checker_resolves_the_same_view_and_item_ids(self) -> None:
        self.assertEqual(check.validate_scene_staging(VISUAL, BOARD), [])
        board = BOARD.replace("VIEW-EP003-FINANCE-MAIN", "VIEW-MISSING", 1)
        errors = check.validate_scene_staging(VISUAL, board)
        self.assertTrue(any("空间视图不存在" in error for error in errors), errors)

    def test_main_checker_rejects_invalid_position_fields(self) -> None:
        board = BOARD.replace("｜侧：east｜", "｜侧：left｜")
        errors = check.validate_scene_staging(VISUAL, board)
        self.assertTrue(any("人物位置字段无效" in error for error in errors), errors)

    def test_main_checker_requires_picture_box_and_valid_origin(self) -> None:
        visual = VISUAL.replace("0.20, 0.44, 0.80, 0.72", "无")
        errors = check.validate_scene_staging(visual, BOARD)
        self.assertTrue(any("必须写图框坐标" in error for error in errors), errors)
        visual = VISUAL.replace("认图来源：picture", "认图来源：estimated")
        errors = check.validate_scene_staging(visual, BOARD)
        self.assertTrue(any("认图来源只能是" in error for error in errors), errors)

    def test_main_checker_checks_extras_placement(self) -> None:
        board = BOARD.replace("- 群演：2｜长桌西侧南端", "- 群演：2")
        errors = check.validate_scene_staging(VISUAL, board)
        self.assertTrue(any("有群演时必须写群演位置" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
