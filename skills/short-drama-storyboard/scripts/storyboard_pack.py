#!/usr/bin/env python3
"""Build an offline H3 or Seedance production pack from creator Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Optional


MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "storyboard_pack.py requires Python {}.{}, running {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )


EPISODE_RE = re.compile(r"EP([0-9]{3,})")
SECTION_RE = re.compile(
    r"^## ((?:SHOT|MOTION|GROUP)-[A-Z0-9-]+) · ([^\n]+)$",
    re.MULTILINE,
)
FIELD_RE = re.compile(
    r"^[ \t　]*[-*+][ \t　]*([^：:\n]+)[ \t　]*[：:](.*)$",
    re.MULTILINE,
)
REF_RE = re.compile(
    r"(REF-[A-Z0-9-]+)（顺序：([1-9]\d*)）· "
    r"([^；\n]+?\.(?:png|jpe?g|webp))《([^》\n]+)》"
    r"（(?:用途：([^；）\n]+)；)?控制：([^；）\n]+)；不得控制：([^）\n]+)）",
    re.IGNORECASE,
)
PLAN_RE = re.compile(r"(PLAN-[A-Z0-9-]+)（顺序：", re.IGNORECASE)
PENDING_RE = re.compile(r"待补参考图：([^；。\n]+)")
DURATION_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)")
PROTOCOLS = ("h3", "seedance")


class PackError(ValueError):
    """The creator Markdown cannot be turned into a trustworthy pack."""


def _sections(document: str, prefixes: tuple[str, ...]) -> dict[str, str]:
    boundaries = [match.start() for match in SECTION_RE.finditer(document)]
    result: dict[str, str] = {}
    for match in SECTION_RE.finditer(document):
        if not match.group(1).startswith(prefixes):
            continue
        later = [boundary for boundary in boundaries if boundary > match.start()]
        end = later[0] if later else len(document)
        entry_id = match.group(1)
        if entry_id in result:
            raise PackError(f"entry ID is duplicated: {entry_id}")
        result[entry_id] = document[match.start() : end]
    return result


def _fields(section: str, owner: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for match in FIELD_RE.finditer(section):
        key = match.group(1).strip()
        if key in result:
            raise PackError(f"{owner}: field is duplicated: {key}")
        result[key] = match.group(2).strip()
    return result


def _copyable_prompt(section: str, owner: str) -> str:
    marker = re.search(
        r"^###[ \t　]+可复制(?:通用)?提示词[ \t　]*$",
        section,
        re.MULTILINE,
    )
    if marker is None:
        raise PackError(f"{owner}: missing ### 可复制提示词")
    body = section[marker.end() :]
    following = re.search(r"^#{2,3}[ \t　]+", body, re.MULTILINE)
    if following is not None:
        body = body[: following.start()]
    lines = [line for line in body.splitlines() if line.strip()]
    if not lines or any(not line.startswith(">") for line in lines):
        raise PackError(f"{owner}: copyable prompt must contain only quoted lines")
    prompt = "\n".join(line[1:].lstrip() for line in lines).strip()
    if not prompt:
        raise PackError(f"{owner}: copyable prompt is empty")
    return prompt


def _duration(value: str, owner: str) -> float:
    match = DURATION_RE.search(value)
    if match is None:
        raise PackError(f"{owner}: missing parsable duration")
    seconds = float(match.group(1))
    if seconds <= 0:
        raise PackError(f"{owner}: duration must be positive")
    return seconds


def _members(value: str, owner: str) -> list[str]:
    members = [item.strip() for item in re.split(r"[、,，]", value) if item.strip()]
    if not members or len(members) != len(set(members)):
        raise PackError(f"{owner}: members must be non-empty and unique")
    return members


def _read_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PackError(f"missing creator document: {label}") from exc


def _source_digest(storyboard: str, video: str) -> str:
    payload = (
        "分镜.md\0" + storyboard + "\0视频提示词.md\0" + video
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _safe_project_path(root: Path, value: str) -> Path:
    raw = value.replace("\\", "/")
    pure = PurePosixPath(raw)
    if (
        not raw
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise PackError(f"unsafe project-relative path: {value}")
    target = root / pure
    if not target.resolve().is_relative_to(root):
        raise PackError(f"path escapes project root: {value}")
    return target


def _segment_specs(
    storyboard: str, video: str
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    shots = _sections(storyboard, ("SHOT-",))
    motions = _sections(video, ("MOTION-",))
    groups = _sections(video, ("GROUP-",))
    if not motions:
        raise PackError("视频提示词.md has no MOTION entries")
    motion_meta: dict[str, dict[str, Any]] = {}
    motion_order: dict[str, int] = {}
    covered: set[str] = set()
    for motion_id, section in motions.items():
        fields = _fields(section, motion_id)
        shot_id = fields.get("分镜", "").strip()
        if not shot_id:
            raise PackError(f"{motion_id}: missing 分镜")
        if shot_id not in shots:
            raise PackError(f"{motion_id}: storyboard shot not found: {shot_id}")
        shot_fields = _fields(shots[shot_id], shot_id)
        seconds = _duration(
            fields.get("时长") or shot_fields.get("时长", ""),
            motion_id,
        )
        motion_meta[motion_id] = {
            "motion_id": motion_id,
            "shot_id": shot_id,
            "seconds": seconds,
            "prompt": _copyable_prompt(section, motion_id),
            "shot": shot_fields,
        }
        motion_order[motion_id] = len(motion_order)

    specs: list[dict[str, Any]] = []
    for group_id, section in groups.items():
        fields = _fields(section, group_id)
        member_ids = _members(fields.get("成员", ""), group_id)
        missing = [member for member in member_ids if member not in motions]
        if missing:
            raise PackError(f"{group_id}: unknown members: {', '.join(missing)}")
        if covered.intersection(member_ids):
            raise PackError(f"{group_id}: a MOTION belongs to more than one GROUP")
        positions = [motion_order[member] for member in member_ids]
        if positions != list(range(positions[0], positions[0] + len(positions))):
            raise PackError(f"{group_id}: members must be adjacent in source order")
        covered.update(member_ids)
        declared = _duration(fields.get("时长", ""), group_id)
        measured = sum(motion_meta[member]["seconds"] for member in member_ids)
        if abs(declared - measured) > 1e-6:
            raise PackError(
                f"{group_id}: duration {declared:g} does not equal members {measured:g}"
            )
        specs.append(
            {
                "source_id": group_id,
                "members": member_ids,
                "seconds": declared,
                "prompt": _copyable_prompt(section, group_id),
            }
        )
    for motion_id, meta in motion_meta.items():
        if motion_id in covered:
            continue
        specs.append(
            {
                "source_id": motion_id,
                "members": [motion_id],
                "seconds": float(meta["seconds"]),
                "prompt": str(meta["prompt"]),
            }
        )
    specs.sort(key=lambda spec: motion_order[spec["members"][0]])
    return specs, motion_meta, shots


def _shot_references(
    root: Path, shots: dict[str, str], members: list[str], motion_meta: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    references: list[dict[str, Any]] = []
    missing: list[str] = []
    seen_paths: set[str] = set()
    requires_start_frame = False
    for motion_id in members:
        shot_id = str(motion_meta[motion_id]["shot_id"])
        fields = _fields(shots[shot_id], shot_id)
        value = fields.get("输入参考图", "")
        if "文生视频" not in value:
            requires_start_frame = True
        for match in REF_RE.finditer(value):
            slot_id, order, raw_path, label, purpose, _, _ = match.groups()
            if raw_path in seen_paths:
                continue
            seen_paths.add(raw_path)
            path = _safe_project_path(root, raw_path)
            entry = {
                "slot_id": slot_id,
                "order": len(references) + 1,
                "source_order": int(order),
                "path": PurePosixPath(raw_path).as_posix(),
                "label": label,
                "purpose": (purpose or "").strip(),
                "shot_id": shot_id,
                "exists": path.is_file() and not path.is_symlink(),
            }
            if not entry["exists"]:
                missing.append(f"{slot_id}: {raw_path}")
            references.append(entry)
        for plan_id in PLAN_RE.findall(value):
            missing.append(f"{plan_id}: external PLAN slot")
        pending = PENDING_RE.search(value)
        if pending is not None:
            missing.extend(
                item.strip()
                for item in re.split(r"[、,，]", pending.group(1))
                if item.strip()
            )
    if requires_start_frame and not any(
        entry["purpose"] == "起始帧" for entry in references
    ):
        missing.append("起始帧")
    references.sort(
        key=lambda entry: (
            entry["purpose"] != "起始帧",
            int(entry["source_order"]),
        )
    )
    for order, entry in enumerate(references, 1):
        entry["order"] = order
    return references, missing


def _prompt_file(
    protocol: str, segment: dict[str, Any], attachments: list[dict[str, str]]
) -> str:
    lines = [
        f"# {segment['id']}",
        "",
        f"- Source: {segment['source_id']}",
        f"- Duration: {segment['seconds']:g}s",
        "- Attachments:",
    ]
    if attachments:
        lines.extend(
            f"  - {entry['file']}: {entry['source']} — {entry['label']}"
            for entry in attachments
        )
    else:
        lines.append("  - none")
    lines.extend(["", "---", "", str(segment["prompt"]), ""])
    if protocol == "h3":
        lines.insert(0, "H3 offline production prompt")
        lines.insert(1, "")
    else:
        lines.insert(0, "Seedance offline production prompt")
        lines.insert(1, "")
    return "\n".join(lines)


def build_pack(
    episode: Path,
    *,
    project_root: Optional[Path],
    protocol: str,
    out: Optional[Path],
) -> dict[str, Any]:
    episode = episode.expanduser().resolve()
    if EPISODE_RE.fullmatch(episode.name) is None:
        raise PackError("episode directory must use an EP001-style name")
    root = (project_root or episode.parent.parent).expanduser().resolve()
    if not root.is_dir():
        raise PackError(f"project root not found: {root}")
    if protocol not in PROTOCOLS:
        raise PackError("protocol must be h3 or seedance")
    storyboard = _read_text(episode / "分镜.md", "分镜.md")
    video = _read_text(episode / "视频提示词.md", "视频提示词.md")
    specs, motion_meta, shots = _segment_specs(storyboard, video)
    default_out = (
        episode
        / "制作成果"
        / "投产包"
        / protocol
    )
    destination = (out or default_out).expanduser().resolve()
    allowed_root = (episode / "制作成果" / "投产包").resolve()
    if (
        destination == allowed_root
        or not destination.is_relative_to(allowed_root)
    ):
        raise PackError("production pack must be written below 制作成果/投产包")
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise PackError("production pack target is not a regular directory")
        manifest = destination / "manifest.json"
        if not manifest.is_file() or manifest.is_symlink():
            raise PackError("refusing to replace a directory that is not a production pack")
        try:
            previous = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PackError("refusing to replace an unreadable production pack") from exc
        if (
            not isinstance(previous, dict)
            or previous.get("kind") != "storyboard_production_pack"
        ):
            raise PackError("refusing to replace a directory that is not a production pack")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    episode_number = int(EPISODE_RE.fullmatch(episode.name).group(1))
    manifest_segments: list[dict[str, Any]] = []
    try:
        for number, spec in enumerate(specs, 1):
            segment_id = f"E{episode_number:02d}-{number:02d}"
            references, missing = _shot_references(
                root, shots, spec["members"], motion_meta
            )
            segment = {**spec, "id": segment_id}
            directory = temporary / segment_id
            directory.mkdir()
            attachments: list[dict[str, str]] = []
            for entry in references:
                if not entry["exists"]:
                    continue
                source = _safe_project_path(root, entry["path"])
                suffix = source.suffix.casefold()
                target_name = f"f{len(attachments) + 1}{suffix}"
                shutil.copyfile(source, directory / target_name)
                attachments.append(
                    {
                        "file": target_name,
                        "slot_id": entry["slot_id"],
                        "source": entry["path"],
                        "label": entry["label"],
                    }
                )
            prompt_name = "prompt.md" if protocol == "h3" else "seedance.md"
            (directory / prompt_name).write_text(
                _prompt_file(protocol, segment, attachments),
                encoding="utf-8",
            )
            manifest_segments.append(
                {
                    "id": segment_id,
                    "source_id": segment["source_id"],
                    "members": segment["members"],
                    "seconds": segment["seconds"],
                    "prompt": f"{segment_id}/{prompt_name}",
                    "attachments": attachments,
                    "references": references,
                    "missing": missing,
                }
            )
        manifest = {
            "schema_version": "1.0",
            "kind": "storyboard_production_pack",
            "protocol": protocol,
            "episode": episode.name,
            "source_digest": _source_digest(storyboard, video),
            "segments": manifest_segments,
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        backup: Optional[Path] = None
        if destination.exists():
            backup = destination.parent / (
                f".{destination.name}.{uuid.uuid4().hex}.old"
            )
            os.replace(destination, backup)
        try:
            os.replace(temporary, destination)
        except Exception:
            if backup is not None and backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {
        "protocol": protocol,
        "out": str(destination),
        "segments": len(manifest_segments),
        "missing": sum(len(segment["missing"]) for segment in manifest_segments),
        "manifest": str(destination / "manifest.json"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--protocol", choices=PROTOCOLS, required=True)
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = build_pack(
            args.episode,
            project_root=args.project_root,
            protocol=args.protocol,
            out=args.out,
        )
    except PackError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(
        f"{result['segments']} segments -> {result['out']} "
        f"({result['missing']} missing attachments)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
