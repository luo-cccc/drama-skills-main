# Agent Note: Scene Staging Markdown Contract

Status: implemented

## Problem

The storyboard already required prose scene staging, but an interactive top-view
editor needs stable object IDs, normalised geometry, person placement and a
reloadable representation. Keeping that state only in `staging.json` would
create a second source of truth; exporting only a prose sentence would make the
editor unable to restore its geometry.

## Decision

Structured staging is optional and remains inside the existing creator
documents:

- `视觉设定.md` records `### 空间视图 · VIEW-*` sections with fixed `ITEM-*`
  objects, picture boxes and top-view bounds.
- `分镜.md` records each staged scene under
  `## 场景站位 · <scene ID> · <location>` with an explicit `空间视图` reference
  and parseable `人物位置` lines.
- `.short-drama/staging/<EP>.json` is a derived cache carrying a digest of the
  two Markdown sources. It is excluded from delivery and can be deleted.
- `skills/short-drama-storyboard/scripts/staging_tool.py` parses, validates,
  emits opening blocking lines and writes the cache.
- `creator_markdown_check.py` validates the cross-document IDs and fields during
  partial and full checks.
- A project that has only the earlier prose staging block remains valid. The
  new rules activate when a structured view or position line is present.

The coordinate meanings and person vocabulary are adapted from
`shuohao-skills` `novel-staging` under Apache-2.0. The Python implementation,
Markdown-first persistence and cross-document checks are original to this
repository.

## Alternatives considered

- **Continue using a long-lived `staging.json`**
  - Strongest argument: the existing editor already understands that format.
  - Rejected because it creates a second editable source for staging and can
    drift from the storyboard after an ordinary Markdown edit.

- **Export only the prose blocking sentence**
  - Strongest argument: it is the smallest creator-facing output.
  - Rejected because geometry and object identity cannot be reconstructed
    reliably, so reopening the editor would lose state.

- **Require structured staging for every existing project**
  - Strongest argument: one uniform data model is easier to maintain.
  - Rejected because it would break prose-only projects and force creators to
    invent coordinates before they need an editor.

## Consequences

- Editors and validators can now agree on stable IDs and normalised positions.
- The Markdown documents remain readable and authoritative.
- Cache deletion is safe, but reopening the editor recomputes from Markdown.
- Keeping the parser in both the standalone storyboard skill and the main
  checker creates a small duplication. Tests must keep their accepted and
  rejected cases aligned.
- Projects that use structured staging must keep picture and plan bounds up to
  date when a scene image or location layout changes.
