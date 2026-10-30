# Agent Note: Offline Production Pack From Creator Markdown

Status: implemented

## Problem

Creators who submit accepted video prompts through an external model interface
need one folder per generation with the exact prompt, ordered picture
attachments and an explicit list of missing inputs. The existing project export
copies the whole episode but does not build that provider-facing segment shape.

Creating a persistent `storyboard.json` or a second authoring pipeline would
duplicate the storyboard and video-prompt documents.

## Decision

`skills/short-drama-storyboard/scripts/storyboard_pack.py` derives either an H3
or Seedance pack from the current `分镜.md` and `视频提示词.md`.

- Each `GROUP-*` entry becomes one segment folder.
- A `MOTION-*` not covered by a group becomes its own segment.
- Group duration must equal its member motion durations.
- Existing `REF-*` images are copied into the segment with stable `f1`, `f2`
  attachment names. `PLAN-*` and `待补参考图` remain explicit missing entries.
- H3 writes `prompt.md`; Seedance writes `seedance.md`.
- The root manifest records source IDs, members, duration, prompt path,
  attachments, reference slots and missing inputs, plus a digest of both source
  Markdown documents.
- The pack is written below `制作成果/投产包/<protocol>/`, is replaceable only
  when its previous manifest identifies the same pack kind, and can always be
  regenerated.

The pack does not run an adapter and is not a production attempt. The adapter
path remains `$short-drama-produce`.

## Alternatives considered

- **Reuse the existing project export**
  - Strongest argument: one export mechanism and fewer tools.
  - Rejected because project export is organised by creator documents, not by
    one model submission, and does not produce per-segment prompt folders.

- **Persist `storyboard.json` and build from it**
  - Strongest argument: machine parsing would be simpler.
  - Rejected because it creates another editable source that can drift from the
    accepted Markdown.

- **Only support H3**
  - Strongest argument: the current video prompt document already carries H3
    structure most directly.
  - Rejected because the accepted Seedance dialect needs the same attachment
    ordering and missing-input evidence.

## Consequences

- External submissions can use a predictable directory structure while the
  project retains only its Markdown sources.
- The pack can be deleted and rebuilt after any accepted document change.
- The current tool validates group arithmetic and attachment order; broader H3
  alignment remains the owner of `video-prompts` and the cross-document checker.
- A pack with missing attachments is still useful for discovering gaps, but its
  manifest must be read before submission.
