# 从 Shuohao JSON 项目迁移

`tools/migrate_shuohao.py` 把 Shuohao 的大纲、角色、美术、剧本、站位和分镜 JSON
一次性转换成 Drama Skills 的项目目录与创作者 Markdown。迁移完成后，运行时不依赖旧 JSON。

## 运行

在包含六个 JSON 的项目目录里，脚本会排除 `test-fixtures`，优先选择 `examples/`：

```bash
python tools/migrate_shuohao.py \
  --source-root /path/to/project \
  --out /path/to/new-drama-project \
  --title "剧名"
```

如果目录里不止一套同名材料，显式指定：

```bash
python tools/migrate_shuohao.py \
  --source-root /path/to/project \
  --out /path/to/new-drama-project \
  --outline /path/to/outline.json \
  --cast /path/to/cast.json \
  --art /path/to/art.json \
  --script /path/to/script.json \
  --staging /path/to/staging.json \
  --storyboard /path/to/storyboard.json
```

已有分镜图按 Shuohao 的 `<段号>/fN.png` 结构放置时，可一起迁入：

```bash
python tools/migrate_shuohao.py \
  --source-root /path/to/project \
  --frames-root /path/to/storyboard-output \
  --out /path/to/new-drama-project
```

目标目录必须不存在或为空；脚本不会覆盖已有项目。

## 产物

- `项目开发/改编大纲.md`
- `项目开发/迁移来源.md`
- `项目开发/迁移待决.md`
- `剧集/EP*/剧本.md`
- `剧集/EP*/视觉设定.md`
- `剧集/EP*/图片提示词.md`
- 有分镜数据的集：`分镜.md`、`视频提示词.md`
- 找到的分镜图：`剧集/EP*/制作成果/images/`

站位 JSON 会写成地点下的 `### 空间视图` 和分镜中的 `## 场景站位` / `人物位置`，
Dashboard 分镜页会直接绘出俯视平面。

分镜镜头有 `beats` 索引时，迁移器会把对应的剧本动作/台词写成「来源」完整引文，不截断长段落。
动作以“冷开场：”等标签开头时增加 `△ ` 前缀，保留原文并避免被误读为角色对白。
逐块节拍覆盖只证明同场原文承载声明完整，不代替镜头内容的语义审查。`beats` 提到但本镜没有入画的人物会写成
「视觉依据」的画外声明。迁移测试覆盖两集、outline-only、script-only、CRLF、缺少 cast/art/staging/
storyboard、真实分镜图与 `PLAN-START`。

## 边界

- 场次内外性质没有源字段时写「内外」，并列入迁移待决。
- 没有真实分镜图时使用 `PLAN-START`，表示该起始帧仍需创作者提供，不冒充已有文件。
- 原 JSON、HTML 报告、质量门日志和供应商任务不复制。
- 迁移是一次性的。后续修改以新的 Drama Markdown 为准，不回写旧 JSON。
