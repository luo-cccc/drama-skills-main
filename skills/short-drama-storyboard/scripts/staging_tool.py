#!/usr/bin/env python3
"""Parse and validate the optional structured scene-staging contract.

The creator Markdown remains authoritative. This tool derives a small cache
for an interactive staging editor and validates that the editor's data still
points at the current visual locations and fixed objects.

The staging model is adapted from shuohao-skills, Copyright 2026 烁皓,
licensed under Apache-2.0. See THIRD_PARTY_NOTICES.md and
licenses/shuohao-skills-NOTICE.txt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "staging_tool.py requires Python {}.{}, running {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )


SCENE_ID_PATTERN = r"(?:[A-Za-z0-9]+-)+SC[0-9]+"
VIEW_ID_PATTERN = r"VIEW-[A-Z0-9-]+"
ITEM_ID_PATTERN = r"ITEM-[A-Z0-9-]+"
EPISODE_RE = re.compile(r"EP[0-9]{3,}")
HEADING_RE = re.compile(r"^(#{2,3})[ \t　]+(.+)$", re.MULTILINE)
VIEW_HEADING_RE = re.compile(
    r"^###[ \t　]+空间视图[ \t　]*·[ \t　]*("
    + VIEW_ID_PATTERN
    + r")(?:[ \t　]*·[ \t　]*(.*))?$",
    re.MULTILINE,
)
VIEW_HEADING_LOOSE_RE = re.compile(
    r"^###[ \t　]*空间视图.*$",
    re.MULTILINE,
)
LOCATION_HEADING_RE = re.compile(
    r"^##[ \t　]+地点[ \t　]*·[ \t　]*(.+)$",
    re.MULTILINE,
)
ITEM_LINE_RE = re.compile(
    r"^[ \t　]*[-*+][ \t　]*平面物件[ \t　]*[：:](.*)$",
    re.MULTILINE,
)
STAGING_HEADING_RE = re.compile(
    r"^##[ \t　]+场景站位[ \t　]*·[ \t　]*("
    + SCENE_ID_PATTERN
    + r")[ \t　]*·[ \t　]*(.+)$",
    re.MULTILINE,
)
STAGING_HEADING_LOOSE_RE = re.compile(
    r"^##[ \t　]*场景站位.*$",
    re.MULTILINE,
)
PERSON_LINE_RE = re.compile(
    r"^[ \t　]*[-*+][ \t　]*人物位置[ \t　]*[：:](.*)$",
    re.MULTILINE,
)
EXTRAS_LINE_RE = re.compile(
    r"^[ \t　]*[-*+][ \t　]*群演[ \t　]*[：:][ \t　]*([0-9]+)"
    r"(?:[ \t　]*｜[ \t　]*(.*))?$",
    re.MULTILINE,
)
FIELD_RE = re.compile(
    r"^[ \t　]*[-*+][ \t　]*([^：:\n]+)[ \t　]*[：:](.*)$",
    re.MULTILINE,
)
ITEM_RE = re.compile(
    r"^(" + ITEM_ID_PATTERN + r")[ \t　]*《([^》\n]+)》"
    r"[ \t　]*（(.*)）[ \t　]*$"
)
PERSON_NAME_RE = re.compile(r"^([^｜\n]+)[ \t　]*$")

SIDES = ("north", "east", "south", "west", "on")
POSTURES = ("sit", "stand")
FACINGS = (
    "north",
    "northeast",
    "east",
    "southeast",
    "south",
    "southwest",
    "west",
    "northwest",
)
MIN_APART = 0.12
POSITION_KEYS = ("物", "侧", "沿线", "姿态", "朝向", "在场")


@dataclass(frozen=True)
class ViewItem:
    item_id: str
    name: str
    box: Optional[tuple[float, float, float, float]]
    plan: tuple[float, float, float, float]
    seatable: bool


@dataclass(frozen=True)
class SpaceView:
    view_id: str
    label: str
    location: str
    image: str
    read_from: str
    screen_direction: str
    items: tuple[ViewItem, ...]


@dataclass(frozen=True)
class PersonPosition:
    name: str
    present: bool
    item: Optional[str] = None
    side: Optional[str] = None
    along: Optional[float] = None
    posture: Optional[str] = None
    facing: Optional[str] = None


@dataclass(frozen=True)
class SceneStaging:
    scene_id: str
    location: str
    view_id: str
    positions: tuple[PersonPosition, ...]
    extras: int = 0
    extras_where: str = ""


@dataclass(frozen=True)
class StagingDocument:
    views: tuple[SpaceView, ...]
    scenes: tuple[SceneStaging, ...]


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _section_end(text: str, start: int, *, levels: tuple[int, ...]) -> int:
    headings = [
        match.start()
        for match in HEADING_RE.finditer(text, start)
        if len(match.group(1)) in levels
    ]
    return headings[0] if headings else len(text)


def _field_values(body: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in FIELD_RE.finditer(body):
        values[match.group(1).strip()] = match.group(2).strip()
    return values


def _attributes(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in value.split("；"):
        key, separator, raw = part.partition("：")
        if not separator:
            continue
        result[key.strip()] = raw.strip()
    return result


def _coordinates(
    value: str,
    count: int,
    *,
    owner: str,
    file_name: str,
    line: int,
    errors: list[str],
) -> Optional[tuple[float, ...]]:
    pieces = [piece.strip() for piece in re.split(r"[,，]", value)]
    if len(pieces) != count:
        errors.append(
            f"{file_name}: 第 {line} 行: {owner} 的坐标需要 {count} 个 0–1 数值"
        )
        return None
    try:
        numbers = tuple(float(piece) for piece in pieces)
    except ValueError:
        errors.append(
            f"{file_name}: 第 {line} 行: {owner} 的坐标包含非数字"
        )
        return None
    if any(not math.isfinite(number) or number < 0 or number > 1 for number in numbers):
        errors.append(
            f"{file_name}: 第 {line} 行: {owner} 的坐标必须在 0–1 之间"
        )
        return None
    return numbers


def _parse_item(
    value: str,
    *,
    read_from: str,
    file_name: str,
    line: int,
    errors: list[str],
) -> Optional[ViewItem]:
    match = ITEM_RE.fullmatch(value.strip())
    if match is None:
        errors.append(
            f"{file_name}: 第 {line} 行: 平面物件必须写成 "
            "`ITEM-*《名称》（图框：…；平面：…；可坐：是|否）`"
        )
        return None
    item_id, name, raw_attributes = match.groups()
    if not name.strip():
        errors.append(f"{file_name}: 第 {line} 行: {item_id} 缺少名称")
        return None
    attributes = _attributes(raw_attributes)
    missing = [key for key in ("图框", "平面", "可坐") if key not in attributes]
    if missing:
        errors.append(
            f"{file_name}: 第 {line} 行: {item_id} 缺少 {'、'.join(missing)}"
        )
        return None
    raw_box = attributes["图框"]
    box: Optional[tuple[float, ...]]
    if raw_box == "无":
        box = None
    else:
        box = _coordinates(
            raw_box,
            4,
            owner=item_id,
            file_name=file_name,
            line=line,
            errors=errors,
        )
        if box is None:
            return None
    if read_from == "picture" and box is None:
        errors.append(
            f"{file_name}: 第 {line} 行: {item_id} 按真实图片认图时必须写图框坐标"
        )
    plan = _coordinates(
        attributes["平面"],
        4,
        owner=item_id,
        file_name=file_name,
        line=line,
        errors=errors,
    )
    seatable = {"是": True, "否": False}.get(attributes["可坐"])
    if seatable is None:
        errors.append(
            f"{file_name}: 第 {line} 行: {item_id} 的可坐只能写「是」或「否」"
        )
    if plan is None or seatable is None:
        return None
    return ViewItem(item_id, name.strip(), box, plan, seatable)


def parse_views(text: str, errors: list[str]) -> tuple[SpaceView, ...]:
    views: list[SpaceView] = []
    seen: set[str] = set()
    exact_starts = {match.start() for match in VIEW_HEADING_RE.finditer(text)}
    for loose in VIEW_HEADING_LOOSE_RE.finditer(text):
        if loose.start() not in exact_starts:
            errors.append(
                f"视觉设定.md: 第 {_line_number(text, loose.start())} 行: "
                "空间视图标题必须写成 `### 空间视图 · VIEW-* · 名称`"
            )
    for heading in VIEW_HEADING_RE.finditer(text):
        end = _section_end(text, heading.end(), levels=(2, 3))
        body = text[heading.end() : end]
        line = _line_number(text, heading.start())
        view_id = heading.group(1)
        label = (heading.group(2) or "").strip()
        if view_id in seen:
            errors.append(f"视觉设定.md: 第 {line} 行: 空间视图 ID 重复: {view_id}")
            continue
        seen.add(view_id)
        locations = list(LOCATION_HEADING_RE.finditer(text, 0, heading.start()))
        if not locations:
            errors.append(
                f"视觉设定.md: 第 {line} 行: {view_id} 必须写在「## 地点 · 名称」条目内"
            )
            continue
        location = locations[-1].group(1).strip()
        fields = _field_values(body)
        read_from = fields.get("认图来源", "")
        if read_from not in ("picture", "prompt"):
            errors.append(
                f"视觉设定.md: 第 {line} 行: {view_id} 的认图来源只能是 picture 或 prompt"
            )
        items: list[ViewItem] = []
        item_ids: set[str] = set()
        item_names: set[str] = set()
        for item_line in ITEM_LINE_RE.finditer(body):
            item_at = heading.end() + item_line.start()
            item_number = _line_number(text, item_at)
            item = _parse_item(
                item_line.group(1),
                read_from=read_from,
                file_name="视觉设定.md",
                line=item_number,
                errors=errors,
            )
            if item is None:
                continue
            if item.item_id in item_ids:
                errors.append(
                    f"视觉设定.md: 第 {item_number} 行: {view_id} 的物件 ID 重复: "
                    f"{item.item_id}"
                )
                continue
            if item.name in item_names:
                errors.append(
                    f"视觉设定.md: 第 {item_number} 行: {view_id} 的物件名称重复: "
                    f"{item.name}"
                )
                continue
            item_ids.add(item.item_id)
            item_names.add(item.name)
            items.append(item)
        if not items:
            errors.append(
                f"视觉设定.md: 第 {line} 行: {view_id} 至少需要一个平面物件"
            )
        views.append(
            SpaceView(
                view_id=view_id,
                label=label or view_id,
                location=location,
                image=fields.get("图片", ""),
                read_from=read_from,
                screen_direction=fields.get("屏幕方向", ""),
                items=tuple(items),
            )
        )
    return tuple(views)


def _parse_position(
    value: str,
    *,
    line: int,
    errors: list[str],
) -> Optional[PersonPosition]:
    pieces = [piece.strip() for piece in value.split("｜")]
    if not pieces or not PERSON_NAME_RE.fullmatch(pieces[0]):
        errors.append(f"分镜.md: 第 {line} 行: 人物位置缺少人物名")
        return None
    name = pieces[0].strip()
    attributes: dict[str, str] = {}
    for piece in pieces[1:]:
        key, separator, raw = piece.partition("：")
        if not separator or key.strip() not in POSITION_KEYS:
            errors.append(
                f"分镜.md: 第 {line} 行: {name} 的人物位置包含未知字段: {piece}"
            )
            return None
        if key.strip() in attributes:
            errors.append(
                f"分镜.md: 第 {line} 行: {name} 的字段重复: {key.strip()}"
            )
            return None
        attributes[key.strip()] = raw.strip()
    present_text = attributes.get("在场", "是")
    if present_text not in ("是", "否"):
        errors.append(
            f"分镜.md: 第 {line} 行: {name} 的在场只能写「是」或「否」"
        )
        return None
    present = present_text == "是"
    if not present:
        extra = [key for key in attributes if key not in ("在场",)]
        if extra:
            errors.append(
                f"分镜.md: 第 {line} 行: {name} 开场不在时不能写 "
                + "、".join(extra)
            )
        return PersonPosition(name=name, present=False)
    missing = [key for key in ("物", "侧", "沿线", "姿态", "朝向") if key not in attributes]
    if missing:
        errors.append(
            f"分镜.md: 第 {line} 行: {name} 缺少 "
            + "、".join(missing)
        )
        return None
    if re.fullmatch(ITEM_ID_PATTERN, attributes["物"]) is None:
        errors.append(f"分镜.md: 第 {line} 行: {name} 的物必须使用 ITEM-* ID")
        return None
    side = attributes["侧"]
    posture = attributes["姿态"]
    facing = attributes["朝向"]
    if side not in SIDES:
        errors.append(
            f"分镜.md: 第 {line} 行: {name} 的侧必须是 "
            + " / ".join(SIDES)
        )
    if posture not in POSTURES:
        errors.append(
            f"分镜.md: 第 {line} 行: {name} 的姿态必须是 sit 或 stand"
        )
    if facing not in FACINGS:
        errors.append(
            f"分镜.md: 第 {line} 行: {name} 的朝向必须是八个方位之一"
        )
    try:
        along = float(attributes["沿线"])
    except ValueError:
        along = -1
    if along < 0 or along > 1:
        errors.append(
            f"分镜.md: 第 {line} 行: {name} 的沿线必须是 0–1 之间的数值"
        )
    if side == "on" and along != 0.5:
        errors.append(f"分镜.md: 第 {line} 行: {name} 在物件上时沿线应写 0.5")
    if (
        side not in SIDES
        or posture not in POSTURES
        or facing not in FACINGS
        or not math.isfinite(along)
        or along < 0
        or along > 1
    ):
        return None
    return PersonPosition(
        name=name,
        present=True,
        item=attributes["物"],
        side=side,
        along=along,
        posture=posture,
        facing=facing,
    )


def parse_scenes(text: str, errors: list[str]) -> tuple[SceneStaging, ...]:
    scenes: list[SceneStaging] = []
    seen: set[str] = set()
    exact_starts = {match.start() for match in STAGING_HEADING_RE.finditer(text)}
    for loose in STAGING_HEADING_LOOSE_RE.finditer(text):
        if loose.start() not in exact_starts:
            errors.append(
                f"分镜.md: 第 {_line_number(text, loose.start())} 行: "
                "场景站位标题必须写成 `## 场景站位 · <场次 ID> · <地点>`"
            )
    for heading in STAGING_HEADING_RE.finditer(text):
        end = _section_end(text, heading.end(), levels=(2,))
        body = text[heading.end() : end]
        line = _line_number(text, heading.start())
        scene_id = heading.group(1)
        if scene_id in seen:
            errors.append(f"分镜.md: 第 {line} 行: 场景站位 ID 重复: {scene_id}")
            continue
        seen.add(scene_id)
        fields = _field_values(body)
        person_matches = list(PERSON_LINE_RE.finditer(body))
        positions: list[PersonPosition] = []
        for person_line in person_matches:
            person_number = _line_number(text, heading.end() + person_line.start())
            position = _parse_position(
                person_line.group(1), line=person_number, errors=errors
            )
            if position is not None:
                positions.append(position)
        names = [position.name for position in positions]
        if len(names) != len(set(names)):
            errors.append(f"分镜.md: 第 {line} 行: {scene_id} 的人物位置重复")
        if person_matches and not fields.get("空间视图"):
            errors.append(
                f"分镜.md: 第 {line} 行: {scene_id} 有人物位置时必须写空间视图"
            )
        extras = 0
        extras_where = ""
        extras_match = EXTRAS_LINE_RE.search(body)
        if extras_match is not None:
            extras = int(extras_match.group(1))
            extras_where = (extras_match.group(2) or "").strip()
            extras_line = _line_number(text, heading.end() + extras_match.start())
            if extras > 0 and not extras_where:
                errors.append(
                    f"分镜.md: 第 {extras_line} 行: 有群演时必须写群演位置"
                )
            if extras == 0 and extras_where:
                errors.append(
                    f"分镜.md: 第 {extras_line} 行: 没有群演时群演位置留空"
                )
        if positions and not any(position.present for position in positions):
            errors.append(f"分镜.md: 第 {line} 行: {scene_id} 开场一个人都不在")
        scenes.append(
            SceneStaging(
                scene_id=scene_id,
                location=heading.group(2).strip(),
                view_id=fields.get("空间视图", "").strip(),
                positions=tuple(positions),
                extras=extras,
                extras_where=extras_where,
            )
        )
    return tuple(scenes)


def validate_documents(
    visual_text: str, storyboard_text: str
) -> tuple[StagingDocument, list[str]]:
    """Parse both documents and return every structural spatial error."""
    errors: list[str] = []
    views = parse_views(visual_text, errors)
    scenes = parse_scenes(storyboard_text, errors)
    by_id = {view.view_id: view for view in views}
    for scene in scenes:
        if not scene.positions:
            continue
        view = by_id.get(scene.view_id)
        if view is None:
            errors.append(
                f"分镜.md: {scene.scene_id}: 空间视图不存在于《视觉设定.md》: "
                f"{scene.view_id or '<空>'}"
            )
            continue
        items = {item.item_id: item for item in view.items}
        for position in scene.positions:
            if not position.present:
                continue
            item = items.get(position.item or "")
            if item is None:
                errors.append(
                    f"分镜.md: {scene.scene_id}: {position.name} 的物件 "
                    f"{position.item} 不在 {view.view_id} 中"
                )
                continue
            if position.side == "on" and not item.seatable:
                errors.append(
                    f"分镜.md: {scene.scene_id}: {position.name} 站在 {item.name} 上，"
                    "但该物件标记为不可坐"
                )
            if position.side == "on" and position.along != 0.5:
                errors.append(
                    f"分镜.md: {scene.scene_id}: {position.name} 在物件上时沿线应为 0.5"
                )
        groups: dict[tuple[str, str], list[PersonPosition]] = {}
        for position in scene.positions:
            if not position.present or position.side in (None, "on"):
                continue
            groups.setdefault((position.item or "", position.side or ""), []).append(
                position
            )
        for (item_id, side), positions in groups.items():
            ordered = sorted(positions, key=lambda position: position.along or 0)
            for before, after in zip(ordered, ordered[1:]):
                if (after.along or 0) - (before.along or 0) < MIN_APART:
                    errors.append(
                        f"分镜.md: {scene.scene_id}: {before.name} 和 {after.name} "
                        f"叠在 {item_id} 的 {side} 侧，沿线至少拉开 {MIN_APART:g}"
                    )
    return StagingDocument(views=views, scenes=scenes), errors


def load_episode(
    episode: Path,
) -> tuple[StagingDocument, list[str], str, str]:
    visual_path = episode / "视觉设定.md"
    storyboard_path = episode / "分镜.md"
    visual = visual_path.read_text(encoding="utf-8") if visual_path.is_file() else ""
    storyboard = (
        storyboard_path.read_text(encoding="utf-8")
        if storyboard_path.is_file()
        else ""
    )
    document, errors = validate_documents(visual, storyboard)
    if not visual_path.is_file():
        errors.append("缺少创作文档: 视觉设定.md")
    if not storyboard_path.is_file():
        errors.append("缺少创作文档: 分镜.md")
    return document, errors, visual, storyboard


def source_digest(visual: str, storyboard: str) -> str:
    payload = (
        "视觉设定.md\0"
        + visual
        + "\0分镜.md\0"
        + storyboard
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def document_payload(
    episode: str,
    document: StagingDocument,
    visual: str,
    storyboard: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "episode": episode,
        "source_digest": source_digest(visual, storyboard),
        "views": [asdict(view) for view in document.views],
        "scenes": [asdict(scene) for scene in document.scenes],
    }


def write_cache(
    episode: Path,
    document: StagingDocument,
    visual: str,
    storyboard: str,
    *,
    project_root: Optional[Path] = None,
) -> Path:
    root = (project_root or episode.parent.parent).resolve()
    target = root / ".short-drama/staging" / f"{episode.name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        document_payload(episode.name, document, visual, storyboard),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.write("\n")
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return target


def read_cache(
    episode: Path,
    *,
    visual: str,
    storyboard: str,
    project_root: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Return the cache only while it still describes the current Markdown."""
    root = (project_root or episode.parent.parent).resolve()
    target = root / ".short-drama/staging" / f"{episode.name}.json"
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != "1.0"
        or payload.get("episode") != episode.name
        or payload.get("source_digest") != source_digest(visual, storyboard)
    ):
        return None
    return payload


def position_line(position: PersonPosition) -> str:
    if not position.present:
        return f"- 人物位置：{position.name}｜在场：否"
    return (
        f"- 人物位置：{position.name}｜物：{position.item}"
        f"｜侧：{position.side}｜沿线：{position.along:.2f}"
        f"｜姿态：{position.posture}｜朝向：{position.facing}"
    )


def render_scene(scene: SceneStaging) -> str:
    lines = [
        f"## 场景站位 · {scene.scene_id} · {scene.location}",
        f"- 空间视图：{scene.view_id}",
    ]
    lines.extend(position_line(position) for position in scene.positions)
    if scene.extras:
        lines.append(f"- 群演：{scene.extras}｜{scene.extras_where}")
    return "\n".join(lines) + "\n"


def blocking_line(scene: SceneStaging, view: SpaceView) -> str:
    items = {item.item_id: item.name for item in view.items}
    side_text = {
        "north": "北侧",
        "east": "东侧",
        "south": "南侧",
        "west": "西侧",
        "on": "上",
    }
    facing_text = {
        "north": "北",
        "northeast": "东北",
        "east": "东",
        "southeast": "东南",
        "south": "南",
        "southwest": "西南",
        "west": "西",
        "northwest": "西北",
    }
    posture_text = {"sit": "坐", "stand": "站"}
    parts = [
        f"{position.name}{posture_text[position.posture or 'stand']}在"
        f"{items.get(position.item or '', position.item or '')}"
        f"{side_text[position.side or 'north']}，面朝{facing_text[position.facing or 'north']}"
        for position in scene.positions
        if position.present
    ]
    if scene.extras:
        parts.append(f"另有{scene.extras}名群演在{scene.extras_where}")
    elif parts:
        parts.append("没有其他人")
    return f"{scene.scene_id}\t" + "；".join(parts)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("parse", "validate", "blocking", "cache"):
        command = commands.add_parser(name)
        command.add_argument("episode", type=Path)
        command.add_argument("--project-root", type=Path)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parser().parse_args(argv)
    episode = args.episode.expanduser().resolve()
    if not episode.is_dir():
        raise SystemExit(f"episode directory not found: {episode}")
    if EPISODE_RE.fullmatch(episode.name) is None:
        raise SystemExit("episode directory must use an EP001-style name")
    document, errors, visual, storyboard = load_episode(episode)
    if args.command == "validate":
        for error in errors:
            print(f"ERROR: {error}")
        if errors:
            return 1
        print(
            f"OK: {len(document.views)} space views, "
            f"{len(document.scenes)} staged scenes"
        )
        return 0
    if args.command == "parse":
        print(
            json.dumps(
                document_payload(episode.name, document, visual, storyboard),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "cache":
        for error in errors:
            print(f"ERROR: {error}")
        if errors:
            return 1
        target = write_cache(
            episode,
            document,
            visual,
            storyboard,
            project_root=args.project_root,
        )
        print(target)
        return 0
    by_id = {view.view_id: view for view in document.views}
    for scene in document.scenes:
        view = by_id.get(scene.view_id)
        if view is not None:
            print(blocking_line(scene, view))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
