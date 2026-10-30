# Agent Note: Reference-Sheet Anchor And Derived Jobs

Status: implemented

## Problem

Character reference generation needs an accepted front full-body anchor and
several views derived from that exact image. A single production job cannot
produce that sequence because the adapter returns only one round of outputs and
the creator must confirm the anchor before any charged derivation runs.

The standalone `character-refs` workflow also must not disappear when the
project model becomes Drama-first.

## Decision

- `short-drama init --mode reference-only` creates a minimal workspace with
  `short-drama.json`, `参考图提示词.md`, `输入/`, and `production/`.
- A reference-only workspace creates no episode tree and does not require the
  five episode documents.
- Each reference view is one image job whose source is an `IMG-*` section in
  `图片提示词.md` or root `参考图提示词.md`.
- An anchor job records `production_profile: reference-sheet` and
  `reference_stage: anchor`.
- A derived job records `reference_stage: derived`,
  `depends_on_job_id`, and `depends_on_output {path, sha256}`. The parent image
  is also a normal labelled reference binding.
- `prepare`, `confirm`, and `run` verify that the parent job fingerprint is
  current, its latest run succeeded, and the recorded parent output bytes still
  match. A stale anchor changes job status to `needs_reconfirmation`.
- The new fields are optional and represented by a distinct stored-job shape.
  Jobs written before this feature remain readable without migration.

## Alternatives considered

- **One multi-output job containing anchor and derived views**
  - Strongest argument: it presents the whole character set as one operation.
  - Rejected because the adapter cannot consume a newly generated anchor in
    the same response, and a single confirmation would authorize invisible
    later work.

- **Store anchor lineage only in the prompt Markdown**
  - Strongest argument: the creator could inspect the full relationship.
  - Rejected because Markdown cannot prove which confirmed job produced the
    current bytes; preparation would have to trust a hand-written hash.

- **Keep `character-refs` as a separate installation unit**
  - Strongest argument: its standalone workflow would remain untouched.
  - Rejected because it would duplicate confirmation, job recording and adapter
    execution outside the primary production boundary.

## Consequences

- Standalone character reference generation remains available without creating
  a fake episode.
- Derived views cannot be prepared or run after an anchor is missing,
  unconfirmed, failed, superseded, or externally modified.
- A multi-view run intentionally requires more confirmations than one batch
  request; this is the cost of preventing unconfirmed charged derivations.
- Output versions and parent relationships are runtime evidence, not a new
  creator document. The prompt Markdown remains the creative source.
