# Third-party notices

This independently distributed skill includes portions reimplemented or adapted from
shuohao-skills 2.2.1 (Copyright 2026 烁皓), captured on 2026-10-30.
The original Drama Skills portions remain under MIT; this notice does not relicense them.

Upstream source: https://github.com/eternityspring/shuohao-skills

Applicable upstream license and notice are included in this package:

- [Apache License 2.0](licenses/Apache-2.0.txt)
- [Upstream NOTICE](licenses/shuohao-skills-NOTICE.txt)

## Local adaptation scope

空间几何、站位、节拍/资产诊断和只读派生视图的 Python / JavaScript 重实现；原 Dashboard 与安全文件访问仍为本仓原创。

- `scripts/creator_markdown_check.py`
- `scripts/creator_views.py`
- `scripts/dashboard_server.py`
- `assets/dashboard/app.js`

## Upstream source files

- `skills/novel-staging/scripts/novel-staging.mjs`
- `skills/novel-script/scripts/novel-script.mjs`
- `skills/novel-art/scripts/novel-art.mjs`
- `skills/novel-storyboard/scripts/novel-storyboard.mjs`

The implementation is translated to this skill's Python/Markdown runtime and
keeps the skill self-contained. Upstream JSON files and Node runtime modules
are not required by the installed skill.
