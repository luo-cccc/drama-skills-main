# Third-party notices

This independently distributed skill includes portions reimplemented or adapted from
shuohao-skills 2.2.1 (Copyright 2026 烁皓), captured on 2026-10-30.
The original Drama Skills portions remain under MIT; this notice does not relicense them.

Upstream source: https://github.com/eternityspring/shuohao-skills

Applicable upstream license and notice are included in this package:

- [Apache License 2.0](licenses/Apache-2.0.txt)
- [Upstream NOTICE](licenses/shuohao-skills-NOTICE.txt)

## Local adaptation scope

参考图锚点/派生依赖、版本与模型适配经验的 Python 重实现；确认、审计和原子落盘仍为本仓原创。

- `scripts/production_tool.py`
- `scripts/provider_adapters.py`

## Upstream source files

- `skills/character-refs/scripts/character-refs.mjs`
- `skills/character-refs/scripts/core.mjs`
- `skills/character-refs/scripts/models.mjs`
- `skills/character-refs/scripts/png.mjs`

The implementation is translated to this skill's Python/Markdown runtime and
keeps the skill self-contained. Upstream JSON files and Node runtime modules
are not required by the installed skill.
