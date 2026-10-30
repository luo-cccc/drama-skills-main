# Agent Note: Shuohao Migration And Dashboard Scene Plan

Status: implemented

## Problem

Shuohao projects store their accepted structure across six JSON files while
Drama projects use creator Markdown. A migration that copied only scripts would
lose character, art, staging and storyboard decisions. A migration that kept
the JSON beside the Markdown would recreate two editable truths.

The Dashboard also showed structured staging only as key/value rows, so the
new top-view coordinates had no visual use.

## Decision

- `tools/migrate_shuohao.py` discovers `outline/cast/art/script/staging/storyboard`
  JSON, excludes repository `test-fixtures`, and prefers unambiguous `examples/`
  material.
- Migration creates a new Drama project through the normal project initializer.
  It renders adaptation notes, episodes, visual settings, image prompts,
  storyboards and video prompts as Markdown.
- Staging locations become `### 空间视图`; scene places become structured
  `人物位置` lines. No long-lived `staging.json` is copied.
- Real `E01-01/f1.png` style frames can be copied with `--frames-root`.
  Missing frames become `PLAN-START` rather than false `REF-*` claims.
- Source facts that cannot be mapped without guessing go to
  `项目开发/迁移待决.md`.
- `creator_views.py` parses structured views and computes person points from
  item bounds, side and distance along the side.
- The Dashboard board view renders those points as a top-down scene plan with
  fixed/seating objects, characters, facing arrows, extras and absent people.
  Legacy prose-only staging remains the previous text cards.

## Alternatives considered

- **Keep JSON beside Markdown during a transition**
  - Strongest argument: preserves every source field exactly.
  - Rejected because later edits would have no single authority and the project
    would never actually finish migrating.

- **Only migrate script and storyboard**
  - Strongest argument: those are the minimum to generate video.
  - Rejected because character identity, location geography and staging are
    exactly the information montage tends to lose.

- **Render a list of coordinates instead of a plan**
  - Strongest argument: no visual layout code or extra browser testing.
  - Rejected because relative positions, overlap and facing are much harder to
    verify as numbers.

## Consequences

- Existing Shuohao projects can become editable Drama projects and validate
  with the creator Markdown checker.
- Migration is one-way; a source project needing perfect custom-tool
  round-tripping must remain on Shuohao.
- Missing frames and unstated interior/exterior facts are visible as pending,
  not silently invented.
- Dashboard scene plans are read-only. Editing still happens in the owning
  Markdown documents.
