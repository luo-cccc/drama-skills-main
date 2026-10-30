# Third-party notices

This independently distributed skill includes portions reimplemented or adapted from
shuohao-skills 2.2.1 (Copyright 2026 烁皓), captured on 2026-10-30.
The original Drama Skills portions remain under MIT; this notice does not relicense them.

Upstream source: https://github.com/eternityspring/shuohao-skills

Applicable upstream license and notice are included in this package:

- [Apache License 2.0](licenses/Apache-2.0.txt)
- [Upstream NOTICE](licenses/shuohao-skills-NOTICE.txt)

## Local adaptation scope

Markdown 站位校验、开场走位、缓存与离线投产包的 Python 重实现。

- `scripts/staging_tool.py`
- `scripts/storyboard_pack.py`

## Upstream source files

- `skills/novel-staging/scripts/novel-staging.mjs`
- `skills/novel-storyboard/scripts/novel-storyboard.mjs`

The implementation is translated to this skill's Python/Markdown runtime and
keeps the skill self-contained. Upstream JSON files and Node runtime modules
are not required by the installed skill.
