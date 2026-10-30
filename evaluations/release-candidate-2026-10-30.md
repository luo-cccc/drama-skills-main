# 发布候选评估 · 2026-10-30

## 范围

本轮验证 Shuohao 吸收后的发布候选，重点覆盖：

- GPT Image 2 / Qwen Image 3.0 真实参考图适配器与异步任务恢复；
- Dashboard reference-only 版本视图；
- 结构化场景站位的拖拽编辑与 Markdown 回写；
- 逐块节拍覆盖、对白估时和资产诊断；
- Shuohao 迁移语料扩展；
- Windows 实跑、Python 3.9 下限、浏览器与主工作流回归。

本节最初验证使用的导入快照没有 `.git` 元数据，因此当时无法记录提交 SHA，也不能冒充固定提交上的正式发布签核。

## 环境

| 项目 | 值 |
|---|---|
| OS | Windows 10 专业版 10.0.19045，64 位 |
| 主解释器 | Python 3.14.6 |
| 下限解释器 | Python 3.9.25（uv 管理） |
| Node.js | v22.22.2 |
| Ruff | 0.15.10 |
| FFmpeg | 9.0-full_build |
| Browser | Playwright 1.59.0-alpha / Chromium 147，headless |

## 自动验证

主解释器：

```text
python -B -m unittest discover -s tests -q
Ran 800 tests in 87.710s
OK (skipped=49)
```

设置 `PYTHONUTF8=1` 后执行；否则 Windows 的 GBK 子进程解码会把 ffmpeg 和 Node 输出误报为失败。

Python 3.9 下限：

```text
uv Python 3.9.25
Ran 179 tests in 8.424s
OK (skipped=6)
```

下限运行覆盖生产适配器、Dashboard 版本/站位、Drama 诊断、项目锁、creator-first 样例、
Shuohao 真实快照与迁移矩阵、完整主工作流回归。

静态与界面机械检查：

```text
ruff check --no-cache .     -> All checks passed
node --check app.js         -> OK
Impeccable detector         -> []
provider_adapters --selftest -> OK
```

49 个跳过项主要来自 Windows 普通用户无法创建符号链接/目录联接，以及当前 Python 解释器没有
Playwright 包。后者由 Node Playwright 真实浏览器任务单独补偿。

## 迁移语料

实际 Shuohao 快照继续通过完整交叉校验。新增合成矩阵覆盖：

- 单集和多集；
- outline-only；
- script-only，缺少 cast / art / staging / storyboard；
- CRLF JSON；
- 有真实分镜图；
- 无分镜图时的 `PLAN-START`；
- `beats` 回填来源短引文；
- 剧情提到但本镜不入画的人物声明。

多集 CRLF 样例迁移后，两集五文档均通过 `creator_markdown_check.py`。

## 浏览器验证

在 1440×900 与 390×844 两档实际 Chromium 中检查：

- reference-only 项目显示参考图当前版本、输出缩略图与项目文件；
- 无横向页面溢出；
- 结构化俯视站位可拖动人物、切换坐站和朝向、编辑群演；
- 方向键可沿线调整人物；
- 保存后 `分镜.md` 中出现新的 `人物位置`；
- reference-only 与分镜页面的 4 张全页截图均非空、文字未互相遮挡。

验证过程中发现并修复 Windows CRLF 下 `空间视图` / `平面物件` 解析为空的问题。

## 主工作流

`tests.test_workflow_evaluation` 的主工作流回归通过：

- 固定 `让你管账号` 原著；
- 章节索引可重算；
- 剧本索引可字节级重建；
- 剧本、助记节拍、资产、图片提示词、分镜、视频提示词、配音稿、审查均可核对；
- 21 个录制产物保持 `accepted`。

本轮修复了 reference-run 中两处无法闭合的 Markdown 加粗，并沿
`source-analysis:triage → source-analysis:value → develop:brief → develop:episode-map →
EP001:contract` 重新发布、接受；修订说明写明只是加粗闭合的机械修复。

这是 Agent 执行的回归与流程检查，不等同于独立人工创作者实跑。仓库当前没有可声明的独立
human evaluator，因此“人工主工作流评估”仍为待办，不能记为已通过。

## 真实生图

使用 APIMart `GET /v1/models` 只读验证成功，账号目录返回：

```text
gpt-image-2
gpt-image-2-official
gpt-image-2.5-ext
gpt-image-2.5-flare
gpt-image-2.5-sunburst
midjourney
```

使用真实 PNG 参考图的 GPT Image 2 低质量测试 job 已完成：

```text
job_id: API-REFERENCE-20261030
model endpoint family: gpt-image-2
reference: 输入/reference-dashboard.png
role: reference_image
output: production/test/apimart-reference-gpt-image.png
dimensions: 1024x1536
bytes: 2632373
sha256: f20e6c9e543317225552d20122a603198237f4859f347d1b7bc1aaf36be94b60
status: succeeded
```

请求遵守 `preview → explicit confirm → run`。APIMart 返回异步任务 ID 后，适配器轮询现有任务并
下载 PNG；`audit` 报告 `pass`，1 个输出校验通过，0 个失败、0 个未决或修改字节。

人工检查生成图：1024×1536 纵向 mood board，保留暖纸色、深海军蓝和青色强调，没有可读界面文字、
品牌或具体界面布局，与 job 中声明的参考控制范围一致。该观察只证明本次协议与内容边界落实，
不评价通用生成质量。

API key 未写入项目、日志、评估记录或 adapter 配置。
真实供应商任务标识保留在仓库外的本地运行记录，不进入公开评估文档。

Qwen Image 3.0 的 APIMart 异步协议与 ComfyUI 路径均有离线测试，但当前账号模型目录没有
`qwen-image-3.0`，因此没有声称已经完成该账号上的真实 Qwen 出图。

## 跨平台结论

- Windows 10：实跑通过，包含 CRLF、路径锁、FFmpeg 与 Dashboard。
- Python 3.9：相关下限回归通过。
- Linux / macOS：本轮未实跑，不能声称通过。
- 符号链接/目录联接：Windows 普通权限下部分测试跳过；PathPinned 实现仍在无链接场景实跑。
- 真实媒体质量：未评估。技术响应、文件字节与参考约束适配不等于人物一致性或画面质量通过。

## 发布判定

后续的[全仓审查与关闭记录](repository-audit-2026-10-30.md)复现的六类问题已修复：
保存基线与草稿保护、参考图依赖失效、严格节拍来源、跨镜对白容量和 Dashboard 诊断消费均已接通。
另完成 CRLF 编辑定位、三个独立包的许可闭包、八个受影响技能的版本与摘要更新。

代码与离线发布候选：**审查确认的问题已关闭**。当前验证结果如下，不沿用前一轮 800 项结果冒充本次修复证明。

- Python 3.14.6：`python -B -m unittest discover -s tests -q`，832 项，87.569 秒，`OK (skipped=52)`。
- Python 3.9.25：同一全量回归，832 项，86.562 秒，`OK (skipped=52)`。
- 真实浏览器：Playwright 1.58.0 / Chromium 145，26 项，18.281 秒，全部通过；包含冲突恢复、离开保护、拖拽回写、CRLF 编辑定位与诊断展示。
- 桌面 1440×900、窄屏 390×844：检查诊断区和站位图，无横向溢出或文字遮挡，截图保留在仓库外。
- CI 固定 Ruff 0.15.11：`ruff check --no-cache .` 通过。
- CI 固定 Mypy 2.3.0：CI 列出的 13 个源文件通过（Python 3.12 / Linux 类型目标；不冒充 Linux 运行测试）。
- `node --check`：通过；Impeccable detector：`[]`。
- 中央控制脚本固定版本 `c584f3caac2f47168781f7165b38200f1bda2350` 与 ClawHub 0.23.3 SDK：11 个独立包的文件清单、大小、SHA-256、精确依赖和包摘要一致；8 个受影响技能已更新版本。
- 三个受影响技能的第三方说明、Apache-2.0 与 NOTICE 均已进入实际打包清单，来源目标映射通过测试。

52 个跳过项包括在主解释器中未安装的浏览器测试；这 26 项已由独立浏览器运行补齐。
无 Git 元数据、Windows 链接权限和私有发布配置等其余环境限制仍如实保留，没有将跳过项改写成通过。
本轮新增 28 项专项回归、3 项浏览器回归和1 项来源闭包检查，历史用例也按真实结构消费来源与画外声明。

*升级*：旧项目请先核对《分镜.md》的来源声明，每个承载原文块补一对完整引文。
不能只为通过校验引用本镜实际没有承担的内容；机械来源完整不等于创作质量已通过。


验证范围仍未覆盖真实 Qwen、Linux/macOS 和独立人工创作者实跑；本轮按用户要求处理仓库问题，
不追加这些外部验收，也不把它们记为通过。当前没有 Git 元数据，因此本轮没有固定提交上的正式发布签核。

正式发布仍按仓库既有提交流程、受保护检查与维护者发布操作执行；本轮没有调用远程发布。

## 远程同步候选验证 · 2026-10-30

本次从目标仓库 main 的 `7521b302cbedd3507ac4f878670bb664ec6641c4` 承接历史，
以公开 v0.9.2 为共同基准三方合并；保留既有台词专项、打戏、面部表演与画风指导，最终为十二个技能。
此前无 Git 导入快照的结果保留为历史，本阶段在真实 Git 检出上完成以下检查：

- Python 3.14.6：835 项，89.980 秒，`OK (skipped=48)`。
- Python 3.9.25：835 项，89.146 秒，`OK (skipped=48)`。
- 真实浏览器：26 项，22.181 秒，全部通过；复用本机已有 Chromium，不生成外部媒体。
- Ruff 0.15.11、Mypy 2.3.0 的 13 个 CI 源文件和 JavaScript 语法检查通过。
- 十二个技能包通过固定 ClawHub 0.23.3 SDK 清单核对；另从 Git 暂存树导出原始提交字节，逐包验证摘要一致。
- 保留远程原有文件；未将工作区外的供应商项目、缓存、截图或临时日志纳入提交。

这是本机提交前回归与内容同步，尚未执行远程发布、真实 Qwen 或独立人工媒体质量验收。
