#!/usr/bin/env python3
"""One-time migration from Shuohao JSON project materials to Drama Markdown."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable, Optional


MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "migrate_shuohao.py requires Python {}.{}, running {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )


ROOT = Path(__file__).resolve().parents[1]
PROJECT_TOOL = ROOT / "skills/short-drama/scripts/project_tool.py"
KINDS = ("outline", "cast", "art", "script", "staging", "storyboard")
SIZE_LABELS = {
    "extreme-wide": "大远景",
    "wide": "全景",
    "medium": "中景",
    "close": "特写",
    "extreme-close": "大特写",
}
STABILITY_LABELS = {
    "stable": "稳定",
    "slight-shake": "微晃",
    "handheld": "手持",
}


class MigrationError(ValueError):
    """The source cannot be migrated without guessing a project contract."""


def _load_project_tool():
    spec = importlib.util.spec_from_file_location("shuohao_migration_core", PROJECT_TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


project_tool = _load_project_tool()


def _read_json(path: Optional[Path], label: str) -> Optional[dict[str, Any]]:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationError(f"cannot read {label} JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MigrationError(f"{label} JSON must contain an object: {path}")
    return value


def _discover(root: Path, kind: str) -> Optional[Path]:
    matches = sorted(
        path
        for path in root.rglob(f"*-{kind}.json")
        if path.is_file() and not path.is_symlink()
    )
    matches = [
        path for path in matches if "test-fixtures" not in path.parts
    ]
    examples = [path for path in matches if path.parent.name == "examples"]
    if len(examples) == 1:
        return examples[0]
    if len(matches) > 1:
        raise MigrationError(
            f"found more than one {kind} JSON; pass --{kind} explicitly: "
            + ", ".join(str(path) for path in matches)
        )
    return matches[0] if matches else None


def _ascii_id(value: str, fallback: str) -> str:
    found = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()
    return found or fallback


def _quote(prompt: str) -> str:
    lines = prompt.strip().splitlines() or [""]
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def _action_text(value: object) -> str:
    """Keep action labels with colons from becoming screenplay speakers."""
    text = str(value).strip()
    if re.match(r"^[^\s：（）:\[\]#]{1,40}(?:（[^（）\r\n]+）)?[：:]", text):
        return "△ " + text
    return text


def _number_list(value: Any, size: int = 4) -> Optional[list[float]]:
    if not isinstance(value, list) or len(value) != size:
        return None
    try:
        numbers = [float(item) for item in value]
    except (TypeError, ValueError):
        return None
    if any(number < 0 or number > 1 for number in numbers):
        return None
    return numbers


def _coords(value: Optional[list[float]]) -> str:
    return "无" if value is None else ", ".join(f"{number:.4g}" for number in value)


class Migration:
    def __init__(
        self,
        root: Path,
        documents: dict[str, Optional[dict[str, Any]]],
        *,
        destination: Path,
        title: str,
        language: str,
        prompt_language: str,
        aspect_ratio: str,
        frames_root: Optional[Path],
    ) -> None:
        self.root = root
        self.source = documents
        self.destination = destination
        self.title = title
        self.language = language
        self.prompt_language = prompt_language
        self.aspect_ratio = aspect_ratio
        self.frames_root = frames_root
        self.pending: list[str] = []
        self.outline = documents.get("outline") or {}
        self.cast = documents.get("cast") or {}
        self.art = documents.get("art") or {}
        self.script = documents.get("script") or {}
        self.staging = documents.get("staging") or {}
        self.storyboard = documents.get("storyboard") or {}
        self.characters = {
            str(item.get("id")): item
            for item in self.outline.get("characters", [])
            if isinstance(item, dict) and item.get("id")
        }
        self.cast_by_name = {
            str(item.get("name")): item
            for item in self.cast.get("characters", [])
            if isinstance(item, dict) and item.get("name")
        }
        self.scenes = {
            str(item.get("id")): item
            for item in self.art.get("scenes", [])
            if isinstance(item, dict) and item.get("id")
        }
        self.props = {
            str(item.get("id")): item
            for item in self.art.get("props", [])
            if isinstance(item, dict) and item.get("id")
        }
        self.locations = {
            str(item.get("sceneId")): item
            for item in self.staging.get("locations", [])
            if isinstance(item, dict) and item.get("sceneId")
        }
        self.staging_scenes = {
            (int(item.get("ep", 0)), int(item.get("scene", 0))): item
            for item in self.staging.get("scenes", [])
            if isinstance(item, dict)
        }
        self.item_ids: dict[tuple[str, str], str] = {}
        for scene_id, location in self.locations.items():
            for index, item in enumerate(location.get("items", []), 1):
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    self.item_ids[(scene_id, item["name"])] = (
                        f"ITEM-{_ascii_id(scene_id, 'LOCATION')}-{index:02d}"
                    )
        self.episode_outline = {
            int(item.get("ep")): item
            for item in self.outline.get("episodes", [])
            if isinstance(item, dict) and isinstance(item.get("ep"), int)
        }
        self.episode_script = {
            int(item.get("ep")): item
            for item in self.script.get("episodes", [])
            if isinstance(item, dict) and isinstance(item.get("ep"), int)
        }
        self.episode_board = {
            int(item.get("ep")): item
            for item in self.storyboard.get("episodes", [])
            if isinstance(item, dict) and isinstance(item.get("ep"), int)
        }
        self.frames: dict[tuple[int, int], list[Optional[str]]] = {}

    def character_name(self, identifier: str) -> str:
        item = self.characters.get(identifier)
        return str(item.get("name", identifier)) if item else identifier

    def scene_name(self, identifier: str) -> str:
        item = self.scenes.get(identifier)
        return str(item.get("name", identifier)) if item else identifier

    def prop_name(self, identifier: str) -> str:
        item = self.props.get(identifier)
        return str(item.get("name", identifier)) if item else identifier

    def image_prompt_items(self, character_ids: list[str], scene_id: str, prop_ids: list[str]) -> str:
        entries = []
        for character_id in character_ids:
            name = self.character_name(character_id)
            entries.append(f"IMG-{_ascii_id(character_id, 'CHAR')}-SHEET《{name}角色板》（控制：身份、体态、造型）")
        if scene_id:
            entries.append(
                f"IMG-{_ascii_id(scene_id, 'SCENE')}-SHEET《{self.scene_name(scene_id)}场景板》"
                "（控制：空间地理、固定锚点、光向）"
            )
        for prop_id in prop_ids:
            name = self.prop_name(prop_id)
            entries.append(f"IMG-{_ascii_id(prop_id, 'PROP')}-SHEET《{name}道具板》（控制：形状、材质、状态）")
        return "；".join(entries) if entries else "无"

    def visual_basis(
        self,
        character_ids: list[str],
        scene_id: str,
        prop_ids: list[str],
        offscreen_ids: list[str] | None = None,
    ) -> str:
        entries = [
            f"人物「{self.character_name(character_id)}」（控制：身份、体态、造型）"
            for character_id in character_ids
        ]
        if scene_id:
            entries.append(
                f"地点「{self.scene_name(scene_id)}」（控制：空间地理、固定锚点、光向）"
            )
        entries.extend(
            f"道具「{self.prop_name(prop_id)}」（控制：形状、材质、状态）"
            for prop_id in prop_ids
        )
        offscreen = list(dict.fromkeys(offscreen_ids or []))
        if offscreen:
            entries.extend(
                f"画外：人物「{self.character_name(identifier)}」"
                for identifier in offscreen
            )
        return "《视觉设定.md》·" + "；".join(entries) if entries else "无"

    def render_outline(self) -> str:
        outline = self.outline
        params = outline.get("params", {}) if isinstance(outline.get("params"), dict) else {}
        adaptation = outline.get("adaptation", {}) if isinstance(outline.get("adaptation"), dict) else {}
        lines = [
            f"# {self.title} · 改编大纲",
            "",
            "> 从 Shuohao `outline.json` 一次性迁入；后续以本 Markdown 为准。",
            "",
            "## 基本信息",
            f"- 题材：{params.get('genre', '未写明')}",
            f"- 集数：{params.get('episodes', '未写明')}",
            f"- 单集时长：{params.get('minutesPerEpisode', '未写明')} 分钟",
            f"- 改编幅度：{params.get('adaptMode', '未写明')}",
            "",
            "## 改编说明",
            str(adaptation.get("core", "源数据未提供核心改编说明。")),
        ]
        for key, label in (("keep", "保留"), ("cut", "删减"), ("merge", "合并"), ("risks", "风险")):
            items = adaptation.get(key, [])
            if items:
                lines.extend(["", f"### {label}"])
                for item in items:
                    if isinstance(item, dict):
                        lines.append(
                            f"- {item.get('what', '')}：{item.get('why') or item.get('plan', '')}"
                        )
                    else:
                        lines.append(f"- {item}")
        lines.extend(["", "## 人物表"])
        for item in outline.get("characters", []):
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('id', '')} · {item.get('name', '')}（{item.get('tier', '')}）"
                    f"：{item.get('role', '')}；{item.get('arc', '')}"
                )
        lines.extend(["", "## 场景表"])
        for item in outline.get("scenes", []):
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('id', '')} · {item.get('name', '')}"
                    f"{' · 主场景' if item.get('primary') else ''}"
                )
        if outline.get("props"):
            lines.extend(["", "## 叙事道具"])
            for item in outline.get("props", []):
                if isinstance(item, dict):
                    lines.append(
                        f"- {item.get('id', '')} · {item.get('name', '')}：{item.get('function', '')}"
                    )
        lines.extend(["", "## 爽点表"])
        for item in outline.get("beats", []):
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('id', '')} · 第 {item.get('episode', '?')} 集 · "
                    f"{item.get('type', '')} · {item.get('setup', '')} → {item.get('payoff', '')}"
                )
        lines.extend(["", "## 分集"])
        for ep in sorted(self.episode_outline):
            item = self.episode_outline[ep]
            lines.extend(
                [
                    "",
                    f"### EP{ep:03d}",
                    f"- 梗概：{item.get('synopsis', '')}",
                    f"- 钩子：{item.get('hook', '')}",
                    f"- 悬念：{item.get('suspense', '')}",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def scene_entries(self, ep: int) -> list[tuple[int, dict[str, Any]]]:
        source_episode = self.episode_script.get(ep, {})
        return [
            (index, scene)
            for index, scene in enumerate(source_episode.get("scenes", []), 1)
            if isinstance(scene, dict)
        ]

    def source_beats(
        self, ep: int, scene_index: int, cut: dict[str, Any]
    ) -> list[dict[str, Any]]:
        scenes = self.scene_entries(ep)
        if not 0 < scene_index <= len(scenes):
            return []
        flow = scenes[scene_index - 1][1].get("flow", [])
        if not isinstance(flow, list):
            return []
        beats = cut.get("beats")
        indices = [item for item in beats if isinstance(item, int)] if isinstance(beats, list) else []
        if indices:
            first, last = min(indices), max(indices)
            return [
                flow[index - 1]
                for index in range(first, last + 1)
                if 0 < index <= len(flow) and isinstance(flow[index - 1], dict)
            ]
        return []

    def source_reference(self, ep: int, scene_index: int, cut: dict[str, Any]) -> str:
        """Quote the screenplay beats a migrated cut says it carries."""

        scene_id = f"EP{ep:03d}-SC{scene_index:03d}"
        selected = self.source_beats(ep, scene_index, cut)
        quotes: list[str] = []
        for beat in selected:
            value = _action_text(beat["action"]) if "action" in beat else beat.get("line")
            text = str(value or "").strip()
            if not text:
                continue
            compact = re.sub(r"\s+", " ", text)
            quotes.append(compact)
        if not quotes:
            return scene_id
        return scene_id + "".join(f"「{quote}」" for quote in dict.fromkeys(quotes))

    def offscreen_characters(
        self, ep: int, scene_index: int, cut: dict[str, Any]
    ) -> list[str]:
        visible = {
            str(item) for item in cut.get("characters", []) if str(item)
        }
        found: list[str] = []
        source_text = self.source_reference(ep, scene_index, cut)
        for identifier, item in self.characters.items():
            name = str(item.get("name", ""))
            if (
                identifier not in visible
                and name
                and name in source_text
            ):
                found.append(identifier)
        for beat in self.source_beats(ep, scene_index, cut):
            speaker = str(beat.get("speaker", ""))
            if speaker and speaker != "VO" and speaker not in visible:
                found.append(speaker)
        return list(dict.fromkeys(found))

    def render_script(self, ep: int) -> str:
        episode = self.episode_script.get(ep)
        if episode is None:
            raise MigrationError(f"script.json has no episode {ep}")
        lines = [f"# EP{ep:03d} · 第 {ep} 集", ""]
        for scene_index, scene in self.scene_entries(ep):
            scene_id = str(scene.get("sceneId", ""))
            location = self.scene_name(scene_id)
            lighting = str(scene.get("lighting") or "时间未定")
            lines.extend(
                [
                    f"## EP{ep:03d}-SC{scene_index:03d} 内外 · {location} · {lighting}",
                    "",
                ]
            )
            for beat in scene.get("flow", []):
                if not isinstance(beat, dict):
                    continue
                if "action" in beat:
                    lines.extend([_action_text(beat["action"]), ""])
                    continue
                speaker = str(beat.get("speaker", ""))
                if speaker == "VO":
                    who = "画外音"
                    tag = "[VO] "
                else:
                    who = self.character_name(speaker)
                    tag = ""
                delivery = str(beat.get("delivery", "")).strip()
                cue = f"（{delivery}）" if delivery else ""
                lines.append(f"{tag}{who}{cue}：{beat.get('line', '')}")
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def render_visual(self, ep: int) -> str:
        scenes = self.scene_entries(ep)
        scene_ids = [str(scene.get("sceneId", "")) for _, scene in scenes]
        character_ids = []
        prop_ids = []
        for _, scene in scenes:
            character_ids.extend(str(item) for item in scene.get("characters", []))
            prop_ids.extend(str(item) for item in scene.get("props", []))
        character_ids = list(dict.fromkeys(character_ids))
        prop_ids = list(dict.fromkeys(prop_ids))
        lines = [
            f"# EP{ep:03d} 视觉设定",
            "",
            "- 制作形态：从 Shuohao 项目迁入的 AI 短剧设定。",
            f"- 时代锚点：{self.art.get('dynasty', '源数据未写明年代')}。",
            "",
        ]
        for character_id in character_ids:
            outline_item = self.characters.get(character_id, {})
            name = self.character_name(character_id)
            cast = self.cast_by_name.get(name, {})
            persona = cast.get("persona", {}) if isinstance(cast.get("persona"), dict) else {}
            description = "；".join(
                part
                for part in [
                    str(persona.get("gender", "")),
                    str(persona.get("ageRange", "")),
                    str(persona.get("identity", "")),
                    str(persona.get("appearance", "")),
                ]
                if part
            )
            lines.extend(
                [
                    f"## 人物 · {name}",
                    f"- 识别锚点：{description or outline_item.get('role', '源数据未提供外观描述')}。",
                    "- 本集造型：沿用 Shuohao 角色设定图中的常态造型。",
                    f"- 人物弧：{persona.get('arc') or outline_item.get('arc', '')}",
                    f"- 说话方式：{persona.get('temperament', '')}",
                    "- 画面代称：无",
                    "",
                ]
            )
        for scene_id in dict.fromkeys(scene_ids):
            scene = self.scenes.get(scene_id, {})
            name = self.scene_name(scene_id)
            anchors = scene.get("anchors", [])
            anchor_text = "；".join(
                f"{item.get('name', '')}：{item.get('desc', '')}"
                for item in anchors
                if isinstance(item, dict)
            )
            lighting = scene.get("lighting", [])
            lighting_text = "；".join(
                f"{item.get('state', '')}：{item.get('prompt', '')}"
                for item in lighting
                if isinstance(item, dict)
            )
            lines.extend(
                [
                    f"## 地点 · {name}",
                    f"- 设计意图：{scene.get('summary', '')}",
                    f"- 识别锚点：{anchor_text}",
                    f"- 光照状态：{lighting_text}",
                ]
            )
            location = self.locations.get(scene_id)
            if location:
                lines.extend(self.render_space_view(scene_id, location))
            lines.append("")
        for prop_id in prop_ids:
            prop = self.props.get(prop_id, {})
            name = self.prop_name(prop_id)
            anchors = prop.get("anchors", [])
            anchor_text = "；".join(
                f"{item.get('name', '')}：{item.get('desc', '')}"
                for item in anchors
                if isinstance(item, dict)
            )
            states = prop.get("states", [])
            state_text = "；".join(
                f"{item.get('state', '')}：{item.get('prompt', '')}"
                for item in states
                if isinstance(item, dict)
            )
            lines.extend(
                [
                    f"## 道具 · {name}",
                    f"- 戏剧功能：{prop.get('summary', '')}",
                    f"- 尺度：{prop.get('scale', '')}",
                    f"- 识别锚点：{anchor_text}",
                    f"- 状态变化：{state_text}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def render_space_view(self, scene_id: str, location: dict[str, Any]) -> list[str]:
        view_id = f"VIEW-{_ascii_id(scene_id, 'SCENE')}-MAIN"
        read_from = str(location.get("readFrom") or "prompt")
        lines = [
            f"### 空间视图 · {view_id} · {location.get('name', self.scene_name(scene_id))}",
            "- 图片：无",
            f"- 认图来源：{'picture' if read_from == 'picture' else 'prompt'}",
            "- 屏幕方向：主视角朝北；平面坐标北在上、西在左。",
        ]
        for item in location.get("items", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            item_id = self.item_ids.get((scene_id, name))
            if not item_id:
                continue
            box = _number_list(item.get("box")) if read_from == "picture" else None
            plan = _number_list(item.get("plan"))
            if plan is None:
                self.pending.append(f"{scene_id} / {name}: 缺少平面坐标，未写入空间视图")
                continue
            round_text = "；圆：是" if item.get("round") else ""
            lines.append(
                f"- 平面物件：{item_id}《{name}》"
                f"（图框：{_coords(box)}；平面：{_coords(plan)}；"
                f"可坐：{'是' if item.get('on') else '否'}{round_text}）"
            )
        return lines

    def render_image_prompts(self, ep: int) -> str:
        scenes = self.scene_entries(ep)
        character_ids = []
        prop_ids = []
        for _, scene in scenes:
            character_ids.extend(str(item) for item in scene.get("characters", []))
            prop_ids.extend(str(item) for item in scene.get("props", []))
        lines = [f"# EP{ep:03d} 图片提示词", ""]
        for character_id in dict.fromkeys(character_ids):
            name = self.character_name(character_id)
            cast = self.cast_by_name.get(name, {})
            image = cast.get("image", {}) if isinstance(cast.get("image"), dict) else {}
            prompt = image.get("sheet") or image.get("prompt") or ""
            lines.extend(
                [
                    f"## IMG-{_ascii_id(character_id, 'CHAR')}-SHEET · {name}角色板",
                    "- 用途：锁定角色身份、体态与常态造型。",
                    "- 参考：无外部参考。",
                    "",
                    "### 可复制提示词",
                    _quote(str(prompt)),
                    "",
                ]
            )
        for scene_id in dict.fromkeys(str(scene.get("sceneId", "")) for _, scene in scenes):
            scene = self.scenes.get(scene_id, {})
            image = scene.get("image", {}) if isinstance(scene.get("image"), dict) else {}
            prompt = image.get("sheet") or image.get("prompt") or ""
            lines.extend(
                [
                    f"## IMG-{_ascii_id(scene_id, 'SCENE')}-SHEET · {self.scene_name(scene_id)}场景板",
                    "- 用途：锁定地点地理、固定锚点和光线。",
                    "- 参考：无外部参考。",
                    "",
                    "### 可复制提示词",
                    _quote(str(prompt)),
                    "",
                ]
            )
        for prop_id in dict.fromkeys(prop_ids):
            prop = self.props.get(prop_id, {})
            image = prop.get("image", {}) if isinstance(prop.get("image"), dict) else {}
            prompt = image.get("sheet") or image.get("prompt") or ""
            lines.extend(
                [
                    f"## IMG-{_ascii_id(prop_id, 'PROP')}-SHEET · {self.prop_name(prop_id)}道具板",
                    "- 用途：锁定道具形状、材质与状态。",
                    "- 参考：无外部参考。",
                    "",
                    "### 可复制提示词",
                    _quote(str(prompt)),
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def frame_path(self, ep: int, segment_id: str, cut_index: int) -> Optional[str]:
        if self.frames_root is None:
            return None
        source = self.frames_root / segment_id / f"f{cut_index}.png"
        if not source.is_file() or source.is_symlink():
            return None
        target = self.destination / f"剧集/EP{ep:03d}/制作成果/images/{segment_id}-f{cut_index}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return target.relative_to(self.destination).as_posix()

    def reference_line(
        self, ep: int, segment_id: str, cut_index: int, shot_id: str
    ) -> str:
        frame = self.frame_path(ep, segment_id, cut_index)
        if frame:
            return (
                f"REF-START（顺序：1）· {frame}《本镜起始帧》"
                "（用途：起始帧；控制：起始构图、站位、人物状态；"
                "不得控制：尚未发生的动作）"
            )
        return (
            f"PLAN-START（顺序：1）· {shot_id}《本镜冻结关键帧》"
            "（用途：起始帧；控制：起始构图、站位、人物状态；"
            "不得控制：尚未发生的动作）"
        )

    def staging_block(self, ep: int, scene_index: int, scene_id: str) -> list[str]:
        location = self.locations.get(scene_id, {})
        if not location:
            return []
        view_id = f"VIEW-{_ascii_id(scene_id, 'SCENE')}-MAIN"
        scene_staging = self.staging_scenes.get((ep, scene_index), {})
        lines = [
            f"## 场景站位 · EP{ep:03d}-SC{scene_index:03d} · {self.scene_name(scene_id)}",
            f"- 空间视图：{view_id}",
        ]
        anchors = self.scenes.get(scene_id, {}).get("anchors", [])
        if anchors:
            lines.append(
                "- 固定锚点："
                + "；".join(
                    str(item.get("name", ""))
                    for item in anchors
                    if isinstance(item, dict)
                )
            )
        cast = scene_staging.get("cast", []) if isinstance(scene_staging, dict) else []
        if cast:
            lines.append(
                "- 轴线："
                + " ↔ ".join(str(item.get("name", "")) for item in cast if isinstance(item, dict))
            )
        for place in scene_staging.get("places", []) if isinstance(scene_staging, dict) else []:
            if not isinstance(place, dict):
                continue
            name = str(place.get("name", ""))
            if not place.get("present"):
                lines.append(f"- 人物位置：{name}｜在场：否")
                continue
            item_id = self.item_ids.get((scene_id, str(place.get("item", ""))))
            if item_id is None:
                self.pending.append(
                    f"EP{ep:03d}-SC{scene_index:03d} / {name}: 站位物件未找到"
                )
                lines.append(f"- 人物位置：{name}｜在场：否")
                continue
            lines.append(
                f"- 人物位置：{name}｜物：{item_id}｜侧：{place.get('side', 'north')}"
                f"｜沿线：{float(place.get('along') or 0.5):.2f}"
                f"｜姿态：{place.get('posture') or 'stand'}"
                f"｜朝向：{place.get('facing') or 'north'}"
            )
        extras = int(scene_staging.get("extras") or 0)
        extras_where = str(scene_staging.get("extrasWhere") or "").strip()
        if extras:
            lines.append(f"- 群演：{extras}｜{extras_where}")
        elif extras_where:
            lines.append("- 群演：0")
        else:
            lines.append("- 群演：0")
        lines.extend(["- 变化：无", ""])
        return lines

    def render_storyboard(self, ep: int) -> Optional[str]:
        episode = self.episode_board.get(ep)
        if episode is None:
            return None
        scenes = self.scene_entries(ep)
        lines = [f"# EP{ep:03d} 分镜", ""]
        for scene_index, scene in scenes:
            lines.extend(
                self.staging_block(ep, scene_index, str(scene.get("sceneId", "")))
            )
        shot_number = 1
        for segment in episode.get("segments", []):
            if not isinstance(segment, dict):
                continue
            scene_index = int(segment.get("sceneIndex") or 1)
            scene_id = (
                str(scenes[scene_index - 1][1].get("sceneId", ""))
                if 0 < scene_index <= len(scenes)
                else ""
            )
            for cut_index, cut in enumerate(segment.get("cuts", []), 1):
                if not isinstance(cut, dict):
                    continue
                shot_id = f"SHOT-EP{ep:03d}-{shot_number:03d}"
                shot_number += 1
                size = SIZE_LABELS.get(str(cut.get("size")), str(cut.get("size", "")))
                framing = "，".join(
                    part
                    for part in [
                        size,
                        str(cut.get("cameraPosition", "")),
                        str(cut.get("lens", "")),
                    ]
                    if part
                )
                camera = "；".join(
                    part
                    for part in [
                        str(cut.get("camera", "")),
                        STABILITY_LABELS.get(str(cut.get("stability")), ""),
                    ]
                    if part
                )
                characters = [
                    str(item)
                    for item in cut.get("characters", [])
                    if str(item) in self.characters
                ]
                props = [
                    str(item)
                    for item in cut.get("props", [])
                    if str(item) in self.props
                ]
                frame = str(cut.get("frame", ""))
                for identifier, name in (
                    (character_id, self.character_name(character_id))
                    for character_id in self.characters
                ):
                    if name and name in frame and identifier not in characters:
                        characters.append(identifier)
                lines.extend(
                    [
                        f"## {shot_id} · 迁入镜头 {shot_number - 1:03d}",
                        f"- 来源：{self.source_reference(ep, scene_index, cut)}",
                        f"- 时长：{float(cut.get('seconds') or 0):g}s",
                        "- 目的：保留 Shuohao 原分镜的叙事职责。",
                        f"- 景别/机位：{framing or '源数据未写景别'}",
                        f"- 运镜：{camera or '源数据未写运镜'}",
                        f"- 起点：{frame or '按冻结关键帧起始状态'}",
                        f"- 唯一动作：{cut.get('shot', '')}",
                        f"- 终点：{cut.get('note') or '镜头正文完成后的可见状态'}",
                        f"- 图片提示词项：{self.image_prompt_items(characters, scene_id, props)}",
                        f"- 输入参考图：{self.reference_line(ep, str(segment.get('id', f'E{ep:02d}-01')), cut_index, shot_id)}",
                        f"- 视觉依据：{self.visual_basis(characters, scene_id, props, self.offscreen_characters(ep, scene_index, cut))}",
                        f"- 声音：{segment.get('soundscape', '')}；{cut.get('sfx', '')}",
                        "",
                        "### 冻结关键帧提示词",
                        _quote(frame or cut.get("shot", "")),
                        "",
                    ]
                )
        return "\n".join(lines).rstrip() + "\n"

    def render_video_prompts(self, ep: int) -> Optional[str]:
        episode = self.episode_board.get(ep)
        if episode is None:
            return None
        lines = [f"# EP{ep:03d} 视频提示词", ""]
        shot_number = 1
        for segment_index, segment in enumerate(episode.get("segments", []), 1):
            if not isinstance(segment, dict):
                continue
            members = []
            cuts = [item for item in segment.get("cuts", []) if isinstance(item, dict)]
            for cut_index, cut in enumerate(cuts, 1):
                shot_id = f"SHOT-EP{ep:03d}-{shot_number:03d}"
                motion_id = f"MOTION-EP{ep:03d}-{shot_number:03d}"
                shot_number += 1
                members.append(motion_id)
                reference = self.reference_line(
                    ep,
                    str(segment.get("id", f"E{ep:02d}-01")),
                    cut_index,
                    shot_id,
                )
                lines.extend(
                    [
                        f"## {motion_id} · 迁入镜头 {shot_number - 1:03d}",
                        f"- 分镜：{shot_id}",
                        f"- 时长：{float(cut.get('seconds') or 0):g}s",
                        "- 生成方式：图生视频",
                        f"- 输入参考图：{reference}",
                        f"- 静态视觉锚点：{cut.get('frame', '')}",
                        f"- 起始帧：{cut.get('frame', '')}",
                        f"- 状态链：{cut.get('frame', '')} → {cut.get('shot', '')} → {cut.get('note') or '完成'}",
                        f"- 终点：{cut.get('note') or '镜头正文完成后的可见状态'}",
                        "",
                        "### 可复制提示词",
                        _quote(str(cut.get("shot", ""))),
                        "",
                    ]
                )
            if members:
                duration = sum(float(item.get("seconds") or 0) for item in cuts)
                lines.extend(
                    [
                        f"## GROUP-EP{ep:03d}-{segment_index:02d} · 迁入生成段 {segment_index:02d}",
                        f"- 成员：{'、'.join(members)}",
                        f"- 时长：{duration:g}s",
                        f"- 理由：Shuohao 原段 {segment.get('id', '')} 的一次生成边界。",
                        "",
                        "### 可复制提示词",
                        _quote(str(segment.get("h3Prompt", ""))),
                        "",
                    ]
                )
        return "\n".join(lines).rstrip() + "\n"

    def render_pending(self) -> str:
        lines = [
            f"# {self.title} · 迁移待决",
            "",
            "以下内容来自源项目，但无法在不猜测的情况下无损映射到 Drama Markdown：",
            "",
        ]
        if not self.pending:
            lines.append("- 没有发现阻断迁移的结构缺口。")
        else:
            lines.extend(f"- {item}" for item in dict.fromkeys(self.pending))
        lines.extend(
            [
                "- 场次的内外性质源数据未逐场声明，剧本标题暂写「内外」。",
                "- 缺少实际分镜图时，分镜与视频提示词写入 `PLAN-START`，不冒充已有图片。",
                "- 原有 JSON、HTML 报告与质量门日志没有复制；迁移结果以本文档和五份 Markdown 为准。",
            ]
        )
        return "\n".join(lines) + "\n"

    def run(self) -> dict[str, Any]:
        if self.destination.exists() and any(self.destination.iterdir()):
            raise MigrationError("destination must be absent or empty")
        episode_numbers = sorted(
            set(self.episode_script)
            | set(self.episode_outline)
            | set(self.episode_board)
        )
        if not episode_numbers:
            raise MigrationError("source has no episodes to migrate")
        target_seconds = next(
            (
                float(item.get("targetSeconds"))
                for item in self.episode_script.values()
                if item.get("targetSeconds") is not None
            ),
            None,
        )
        project_tool.initialize_project(
            self.destination,
            title=self.title,
            language=self.language,
            prompt_language=self.prompt_language,
            aspect_ratio=self.aspect_ratio,
            episode_count=len(episode_numbers),
            target_seconds_per_episode=target_seconds,
            suite_root=ROOT / "skills/short-drama",
        )
        development = self.destination / "项目开发"
        development.mkdir(parents=True, exist_ok=True)
        (development / "改编大纲.md").write_text(
            self.render_outline(), encoding="utf-8"
        )
        (development / "迁移来源.md").write_text(
            "# Shuohao 迁移来源\n\n"
            + "\n".join(
                f"- {kind}: {path}"
                for kind, path in self.source_paths.items()
                if path is not None
            )
            + "\n",
            encoding="utf-8",
        )
        documents = 0
        for ep in episode_numbers:
            episode_dir = self.destination / f"剧集/EP{ep:03d}"
            episode_dir.mkdir(parents=True, exist_ok=True)
            if ep in self.episode_script:
                (episode_dir / "剧本.md").write_text(
                    self.render_script(ep), encoding="utf-8"
                )
                documents += 1
            if ep in self.episode_script:
                (episode_dir / "视觉设定.md").write_text(
                    self.render_visual(ep), encoding="utf-8"
                )
                (episode_dir / "图片提示词.md").write_text(
                    self.render_image_prompts(ep), encoding="utf-8"
                )
                documents += 2
            storyboard = self.render_storyboard(ep)
            if storyboard is not None:
                (episode_dir / "分镜.md").write_text(storyboard, encoding="utf-8")
                documents += 1
            video = self.render_video_prompts(ep)
            if video is not None:
                (episode_dir / "视频提示词.md").write_text(video, encoding="utf-8")
                documents += 1
        (development / "迁移待决.md").write_text(
            self.render_pending(), encoding="utf-8"
        )
        return {
            "out": str(self.destination),
            "episodes": episode_numbers,
            "documents": documents,
            "pending": list(dict.fromkeys(self.pending)),
        }

    @property
    def source_paths(self) -> dict[str, Optional[Path]]:
        return {
            kind: (
                self.source.get(kind, {}).get("_path")
                if isinstance(self.source.get(kind), dict)
                else None
            )
            for kind in KINDS
        }


def _source_meta(document: Optional[dict[str, Any]], path: Optional[Path]) -> Optional[dict[str, Any]]:
    if document is None:
        return None
    return {**document, "_path": str(path) if path else ""}


def migrate(
    *,
    source_root: Path,
    destination: Path,
    outline: Optional[Path] = None,
    cast: Optional[Path] = None,
    art: Optional[Path] = None,
    script: Optional[Path] = None,
    staging: Optional[Path] = None,
    storyboard: Optional[Path] = None,
    title: Optional[str] = None,
    language: Optional[str] = None,
    prompt_language: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    frames_root: Optional[Path] = None,
) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    if not source_root.is_dir():
        raise MigrationError(f"source root not found: {source_root}")
    destination = destination.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise MigrationError("destination must be absent or empty")
    explicit = {
        "outline": outline,
        "cast": cast,
        "art": art,
        "script": script,
        "staging": staging,
        "storyboard": storyboard,
    }
    paths = {
        kind: (path.expanduser().resolve() if path else _discover(source_root, kind))
        for kind, path in explicit.items()
    }
    documents = {
        kind: _source_meta(_read_json(paths[kind], kind), paths[kind])
        for kind in KINDS
    }
    if documents["script"] is None and documents["outline"] is None:
        raise MigrationError("source needs at least script.json or outline.json")
    inferred_title = (
        title
        or (documents["outline"] or {}).get("source")
        or (documents["cast"] or {}).get("source")
        or (documents["script"] or {}).get("source")
        or source_root.name
    )
    migration = Migration(
        source_root,
        documents,
        destination=destination,
        title=str(inferred_title),
        language=language
        or str((documents["outline"] or {}).get("lang") or "zh-CN"),
        prompt_language=prompt_language
        or str((documents["storyboard"] or {}).get("promptLang") or "zh"),
        aspect_ratio=aspect_ratio
        or str((documents["storyboard"] or {}).get("aspectRatio") or "16:9"),
        frames_root=frames_root.expanduser().resolve() if frames_root else None,
    )
    return migration.run()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    for kind in KINDS:
        parser.add_argument(f"--{kind}", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--language")
    parser.add_argument("--prompt-language")
    parser.add_argument("--aspect-ratio", choices=("16:9", "9:16"))
    parser.add_argument("--frames-root", type=Path)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = migrate(
            source_root=args.source_root,
            destination=args.out,
            outline=args.outline,
            cast=args.cast,
            art=args.art,
            script=args.script,
            staging=args.staging,
            storyboard=args.storyboard,
            title=args.title,
            language=args.language,
            prompt_language=args.prompt_language,
            aspect_ratio=args.aspect_ratio,
            frames_root=args.frames_root,
        )
    except MigrationError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(
        f"migrated {len(result['episodes'])} episodes, "
        f"{result['documents']} documents -> {result['out']}"
    )
    if result["pending"]:
        print(f"{len(result['pending'])} pending decisions recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
