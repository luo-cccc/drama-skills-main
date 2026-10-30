# Agent Note: 以 Drama Skills 为主吸收 Shuohao Skills

Status: proposed

## Problem

当前工作区里有两个覆盖面高度重叠的 AI 短剧 skill 仓库：

- `drama-skills-main`：以创作 Markdown 为唯一内容源，覆盖从原著/点子到剧本、资产、分镜、
  图片与视频提示词、确认后生产、剪辑、审查和 Dashboard 的完整项目流程。
- `shuohao-skills-main`：以多份 JSON 为上下游契约，覆盖小说大纲、角色、美术、剧本、站位和
  分镜，提供零依赖 Node 脚本、确定性质量门、HTML 工具报告与 H3/Seedance 投产包。

如果两个仓库长期并行，会出现三套成本：

1. 同一故事事实在 Markdown 与 JSON 中有两个来源，跨仓修改后无法判断哪一份已被接受。
2. 剧本、镜头、时长、参考图和视频方言的规则会在两套解析器与两套测试里漂移。
3. 两个仓库都需要维护报告、导出、安装与发布，使用者还要决定从哪个入口开始。

简单地把 `shuohao-skills-main` 整体复制进来也不可行：它会引入第二套创作真相、第二套 Node
运行时、与现有技能所有权冲突的 JSON schema，以及不适用于 Drama Skills 的通用硬门槛。

本提案要解决的是“如何吸收能力”，不是“如何把两个仓库并排装在一起”。

## Proposal

### 1. 主仓与产品边界

以 `drama-skills-main` 作为唯一主仓和产品入口：

- 项目初始化、跨阶段路由、Dashboard、生产确认、剪辑、审查和交付继续由
  `$short-drama` 及其现有子技能负责。
- 每集的 `剧本.md`、`视觉设定.md`、`分镜.md`、`图片提示词.md`、
  `视频提示词.md` 仍是唯一创作真相。
- `剪辑单.md` 仍只在进入后期后由剪辑技能维护。
- `shuohao-skills-main` 只作为能力来源，不保留一套平行的创作者入口。
- `staging.json`、`cast.json`、`art.json`、`script.json`、`storyboard.json`、
  `outline.json` 等结构化文件如果继续存在，只能是：
  - 运行期临时状态；
  - 从 Markdown 派生的只读解析结果；
  - 一次性导入/导出格式；
  - 不参与创作者接受、审查或交付判定的缓存。

### 2. 实现语言与依赖边界

吸收后的正式实现只使用 Drama Skills 现有运行时：

- Python 3.9 标准库；
- 原生 HTML/CSS/JS；
- 剪辑继续使用 `ffmpeg` / `ffprobe`；
- 不增加 Node.js 运行时依赖，不把 `.mjs` 工具直接作为正式安装单元。

`shuohao-skills-main` 中值得保留的确定性逻辑要移植为 Python，并用 Python 测试重写行为验证。
现有 Node selftest 只作为迁移阶段的行为对照，不随正式技能分发。

### 3. 能力归属

| Shuohao 来源 | 吸收内容 | Drama 归属 | 规则级别 |
|---|---|---|---|
| `novel-outline` | 分集覆盖、爽点间隔、钩子、角色/场景预算等诊断思路 | `$short-drama-develop`、`$short-drama-novel-analyze` | 项目已声明数值为 `reviewed_invariant`；通用阈值为 `craft_default` |
| `novel-characters` | 角色身份、造型、跨视图锚点、设定图版面与多语言经验 | `$short-drama-assets`、`$short-drama-image-prompts` | 视觉方向为 `craft_default`，引用与文件事实为 `structural_invariant` |
| `character-refs` | 正面全身锚点、派生视图、版本/过期链、模型适配与锚点确认 | `$short-drama-produce`，提示词仍由 `$short-drama-image-prompts` 拥有 | 确认与输入绑定为 `structural_invariant`；视图档位为 `craft_default` |
| `novel-art` | 场景/道具识别锚点、状态变体、白底无人无手参考板检查 | `$short-drama-assets`、`$short-drama-image-prompts` | 参考板范围内为 `reviewed_invariant`；摄影风格为 `taste_option` |
| `novel-script` | 节拍覆盖、对白估时、冷开场与爽点认领检查 | `$short-drama-write`、跨文档检查器 | 能被项目声明机械核对的部分为 `reviewed_invariant`；节拍粒度与语速默认为 `craft_default` |
| `novel-staging` | 场景物件识别、开场站位、平面视角、群演位置与可交互调整 | `$short-drama-storyboard` | 已声明站位引用和人物完整性为 `structural_invariant`；是否需要独立平面工具为 `craft_default` |
| `novel-storyboard` | 段/切层级、节拍认领、镜头容量、H3 对齐、Seedance 投产包 | `$short-drama-storyboard`、`$short-drama-video-prompts`、`$short-drama-produce` | 引用、时长和方言一致性为 `structural_invariant`；2–5 秒等数值只能作为模型或项目默认值 |
| 根目录报告组装器 | 分段报告、批次视图、配音对齐、导出摘要的交互经验 | `$short-drama` Dashboard 和 `export` | 展示能力为 `craft_default`，不形成新真相 |

不直接吸收：

- 不保留 `novel-outline`、`novel-characters`、`novel-art`、`novel-script` 等独立技能入口。
- 不把 `shuohao-skills-main` 的 JSON schema 设为 `drama-skills` 的公共创作契约。
- 不把“每切 2–5 秒”“每景 3–5 个锚点”“固定角色数”等供应商或题材默认值升级为全项目硬门槛。
- 不复制整套报告页面作为第二套 Dashboard。

### 4. 核心落地契约

#### 4.1 场景站位与编辑器往返

站位编辑器必须能把可编辑数据写回 Markdown，再从 Markdown 重建。
不允许只保存一句自然语言走位，也不允许把长期编辑状态藏在不可恢复的浏览器缓存里。

《视觉设定.md》的地点条目增加一个 `### 空间视图 · VIEW-*` 小节，用来记录场景图里实际可见的
物件和平面位置：

```markdown
### 空间视图 · VIEW-EP001-OFFICE-MAIN
- 图片：REF-OFFICE-SHEET（顺序：1）· 剧集/EP001/制作成果/images/office-sheet.png《办公室场景板》
- 认图来源：picture
- 屏幕方向：主视角机位在南侧向北看，画面左为西、右为东
- 平面物件：ITEM-DESK《办公桌》（图框：0.16, 0.44, 0.84, 0.72；平面：0.18, 0.38, 0.82, 0.64；可坐：是）
- 平面物件：ITEM-WINDOW《百叶窗》（图框：0.00, 0.08, 0.18, 0.46；平面：0.00, 0.08, 0.16, 0.46；可坐：否）
```

`VIEW-*` 和 `ITEM-*` 在本项目内稳定且唯一。坐标统一为 0–1；图框采用
`左,上,右,下`，平面采用 `西,北,东,南`。没有场景图时可以把「认图来源」写成 `prompt`，
但必须标明这是按提示词推算、尚未按真实图片核对。

《分镜.md》的场景站位保留现有可读字段，同时增加可解析的人物位置行：

```markdown
## 场景站位 · EP001-SC001 · 旧办公室
- 空间视图：VIEW-EP001-OFFICE-MAIN
- 固定锚点：门在西南侧；办公桌在房间中央；百叶窗在东墙。
- 轴线：许棠 ↔ 赵经理；working side：百叶窗一侧。
- 人物位置：许棠｜物：ITEM-DESK｜侧：west｜沿线：0.50｜姿态：stand｜朝向：east
- 人物位置：赵经理｜物：ITEM-DESK｜侧：east｜沿线：0.50｜姿态：sit｜朝向：west
- 群演：2｜长桌西侧南端
- 变化：无。
```

`侧` 只接受 `north/east/south/west/on`；`沿线` 只接受 0–1；`姿态` 只接受
`sit/stand`；`朝向` 只接受八个方位。后来才入场的人写 `在场：否`，不得省掉人物行。

`.short-drama/staging/<EP>.json` 可以作为编辑器缓存存在，但必须满足：

- 不是创作真相，删除后不影响项目；
- 记录其来源 Markdown 的 SHA256，Markdown 变化后缓存立即失效；
- 能够从 Markdown 和场景图重建；
- 不进入交付包；
- 编辑器导出时只写回《分镜.md》和《视觉设定.md》的正式 Markdown。

往返验收必须证明：

- 同一份 Markdown 导入编辑器再导出，语义和坐标不变；
- 手工修改人物侧、沿线、姿态或朝向，编辑器能正确读取；
- 删除缓存后，只凭项目文件仍能重新打开并编辑；
- 无法解析的 Markdown 不让编辑器静默覆盖，改为只读并指出具体行。

#### 4.2 角色参考图的 job graph

参考图生产不能把所有视图合并成一个 job。一个 job 的 adapter 响应只有一轮输出，
无法在同一调用内完成“先生成锚点、确认、再拿真实锚点派生”。

每个视图使用独立 job：

```text
reference-sheet-anchor
  └── reference-sheet-derived: face-front
  └── reference-sheet-derived: side-full
  └── reference-sheet-derived: back-full
  └── reference-sheet-derived: detail-*
```

job 在现有 schema 上增加有边界字段：

- `production_profile`：固定为 `reference-sheet`；
- `reference_stage`：`anchor` 或 `derived`；
- `depends_on_job_id`：派生 job 的锚点或确实被允许的父视图；
- `depends_on_output`：父 job 的输出版本与 SHA256；
- `source_entry`：当前视图对应的 `IMG-*` 条目；
- `reference_bindings`：真实锚点或确认视图，用途写身份、造型或细节控制范围；
- `outputs`：这个视图唯一的目标文件。

执行规则：

1. 锚点 job 只生成 `front-full`，经创作者明确确认并成功运行后才能派生；
2. 派生 job 在 `prepare` 时核对父 job 已成功、父输出当前 SHA256 未变、锚点仍为已确认状态；
3. 父图或文字描述变化后，现有派生结果标为过期，但不删除；
4. 每个派生 job 仍需自己展示预览并取得本次明确确认，不用锚点确认代替；
5. 批量预览可以一次列出多个派生 job，但不能把多个 job 合并成一次确认；
6. 运行时依赖写入现有 `.short-drama/production/jobs/`、`confirmations/` 和 `runs/`
   记录，不另建创作文档。

PNG 元数据写入 `drama:reference-id`、`drama:model`、`drama:lineage`；
迁移期读取旧 `shuohao:*` 字段，但新产物不继续生成旧命名空间。

独立角色参考图能力通过 `$short-drama-produce` 的 **reference-only workspace** 保留：

- `$short-drama` 初始化 `--mode reference-only` 的最小工作区；
- 工作区只需 `short-drama.json` 和根目录 `参考图提示词.md`；
- `$short-drama-image-prompts` 负责把角色描述拆成锚点和视图 `IMG-*` 条目；
- `$short-drama-produce` 使用同一 job graph，输出到 `production/reference/<角色>/`；
- 不要求创建剧集或五份剧集文档；
- 已有角色图通过显式导入成为参考文件，不靠文件名自动认领。

#### 4.3 视频投产包与 adapter job

保留两条明确路径，但两者读取同一份 Markdown 和使用同一套确定性检查：

1. **离线投产包**：`$short-drama-storyboard` 在用户点名导出时生成可人工挂图的目录包；
2. **内置 adapter job**：`$short-drama-produce` 从《视频提示词.md》建立 job，用于确认后直接调用供应商。

离线投产包是派生交付物，目录为：

```text
剧集/<EP>/制作成果/投产包/<protocol>/
├── manifest.json                 # H3
├── seedance-manifest.json        # Seedance
├── E01-01/
│   ├── prompt.md                 # H3
│   ├── seedance.md               # Seedance
│   └── f1.png … fN.png
└── …
```

规则：

- `protocol` 只接受 `h3` 或 `seedance`；
- `f1.png` 始终对应该段起始帧，其他图按生成时的参考顺序编号；
- manifest 记录段号、时长、切点、附件顺序、缺失文件和生成时源 Markdown 摘要；
- 投产包可以从《分镜.md》《视频提示词.md》和已绑定图片重新生成；
- 它是交付快照，不被反向解析成第二份创作真相；
- adapter job 不要求先生成投产包，投产包也不冒充生产执行记录；
- 两边都必须校验镜头时长、参考角色、方言和 H3 切点是否与源文档一致。

#### 4.4 迁移边界

旧 JSON 只用于一次性迁移，不提供持续双向同步。迁移覆盖整条来源链：

- `outline.json` → `项目开发/` 的分集材料、角色/场景/道具清单；
- `cast.json` → 《视觉设定.md》的人物与造型条目，以及《图片提示词.md》的角色板；
- `art.json` → 《视觉设定.md》的地点、空间视图、道具与状态变体；
- `script.json` → 《剧本.md》；
- `staging.json` → 《视觉设定.md》的空间视图和《分镜.md》的场景站位；
- `storyboard.json` → 《分镜.md》与《视频提示词.md》；
- `asset.json` 与 PNG 元数据 → 参考图的现有版本、父图关系和过期状态。

无法无损映射的内容写入 `项目开发/迁移待决.md`，不自动猜测。迁移器不得把旧 JSON 自动
转成永久伴生文件；迁移完成后删除旧 JSON，项目仍能完整运行。

### 5. 分阶段实施

#### 阶段 0：冻结来源与许可证

目标：把吸收对象变成可追溯而非“从另一个目录随手拷代码”。

- 记录 `shuohao-skills-main` 的版本、来源仓库、获取日期和全部待移植文件的 SHA256 清单，
  清单落到 `docs/third-party/shuohao-skills-2.2.1.json`。
- 建立 `licenses/Apache-2.0.txt`、仓库根 `THIRD_PARTY_NOTICES.md`，复制原
  `NOTICE` 中适用于被吸收部分的版权归属。
- 复制或改写后的源文件保留来源、许可证和修改说明；README 明确区分 MIT 原创部分与
  Apache-2.0 吸收部分。
- 在删除旧仓库前保存行为夹具：把旧 Node selftest 的典型输入和预期确定性输出复制到
  `tests/fixtures/migration/shuohao-2.2.1/`。正式测试不依赖 Node。
- 对拟移植函数逐项标注旧测试用例，建立“旧行为 → 新行为”对照表。

验收：

- 每个拟复制文件都能追溯到来源快照。
- 许可证与 NOTICE 检查通过。
- 不依赖旧仓库仍然存在于磁盘。

#### 阶段 1：确定契约和所有权

目标：先消除冲突，再移动代码。

- 在 `$short-drama-storyboard` 的阶段契约中定义可选「场景站位」段落，继续使用
  `## 场景站位 · <场次 ID> · <地点>`，并采用 4.1 的人物位置语法。
- 在 `$short-drama-assets` 的阶段契约中定义 4.1 的 `空间视图` 和稳定 `ITEM-*` 语法。
- 明确站位编辑器的标准导出只能写回正式 Markdown；`.short-drama/staging/` 是派生缓存。
- 在 `$short-drama-produce` 契约中新增“参考图生成 job”的语义，仍使用现有
  `prepare -> explicit confirm -> run`，采用 4.2 的锚点与派生 job graph。
- 在 `$short-drama-image-prompts` 中新增参考图板条目的字段约定，确保图片生产的
  `source` 和 `source_entry` 仍指向当前 Markdown。
- 在 `$short-drama-storyboard` 中定义 4.3 的离线投产包；`$short-drama-produce`
  继续负责 adapter job，两者不互相替代。
- 在 `$short-drama` 中增加 reference-only workspace 初始化模式，保留独立角色参考图用法。
- 给每项新规则标注 `structural_invariant` / `reviewed_invariant` /
  `craft_default` / `taste_option`，并登记到 knowhow 索引。
- 把本笔记中的决定拆成可提交的实施 note，再开始行为改动。

验收：

- 每个新增字段只有一个 owner。
- 不新增“第六份创作文档”。
- 所有新规则都能说明触发条件、作用范围和可否由项目档案覆盖。

#### 阶段 2：吸收站位与分镜校验

目标：先吸收最容易形成确定性收益的部分。

- 在 `short-drama-storyboard` 内新增本地 Python 工具，负责：
  - 从《剧本.md》读取场次和出场人物；
  - 从《视觉设定.md》读取地点、空间视图、道具与可见锚点；
  - 生成和校验「场景站位」；
  - 输出每场开场走位句；
  - 导出可选俯视平面编辑器的数据；
  - 把编辑器结果重新导出为 Markdown。
- 俯视平面编辑器可作为独立静态 HTML 报告或 Dashboard 视图；缓存、失效和重建遵守 4.1。
- 把 Shuohao 的站位门移植为局部检查：
  - 出场人物不多不少；
  - 人物只落在已识别物件上；
  - 同一侧不重叠；
  - 后来入场的人物不提前出现在开场；
  - 群演位置必须说明。
- 把分镜中的节拍覆盖、对白时长、镜头起止、参考槽位和 H3 切点对账统一进
  `creator_markdown_check.py` 的局部/全量检查。
- 2–5 秒切镜、段长上限和对白语速只从已接受的模型档案或项目节奏档案读取；
  未声明时作为建议，不伪造硬门。

验收：

- 双人单房、多人桌戏、有人中途入场三类夹具通过。
- 修改剧本场次 ID 后，检查器能指出失效的站位与分镜引用。
- 编辑器导出的 Markdown 与命令行生成结果一致。
- Markdown → 编辑器 → Markdown 的语义和坐标往返一致。
- 删除 `.short-drama/staging/` 后仍能从正式文档重建编辑器。
- 没有产生新的长期创作 JSON。

#### 阶段 3：吸收角色参考图生产

目标：补齐 Drama Skills 当前最明确的能力缺口：从确认后的角色提示词真正生成参考图。

- 在现有 `short-drama-produce` 的 `image` modality 下增加参考图 job profile，不新增
  `character-refs` 公开技能。
- 首张正面全身图是锚点；其余视图用独立派生 job，遵守 4.2 的依赖、确认和失效规则。
- 把视图档位、模型选择、锚点确认、版本递增、父图依赖与过期判定作为运行时元数据，
  写入现有生产 job/attempt 记录和 PNG 元数据。
- 生成图落到 `剧集/<EP>/制作成果/images/`；分镜 owner 再把真实文件绑定为
  `REF-...`，生产工具不自动改创作文档。
- reference-only workspace 输出到 `production/reference/<角色>/`，保留独立角色图用法。
- 移植 Qwen/ComfyUI、Codex、OpenAI Images 和自定义命令适配经验；正式适配仍通过项目外
  adapter config 选择，凭据不进入项目。
- 失败和中断继续走现有 `collect -> audit -> explicit reconfirm -> retry` 规则。

验收：

- 锚点未经确认时，派生视图 fail closed。
- 换锚点、描述或画风后，依赖图被标为过期但不删除。
- 父 job 失败、输出哈希变化或锚点未确认时，派生 job 在 `prepare` 阶段失败。
- fake provider 覆盖成功、失败、超时、中断恢复和重复确认。
- 任何生产 job 仍能追溯到当前《图片提示词.md》条目和明确确认。
- reference-only workspace 不创建剧集，也能完成锚点、派生、确认与重出。

#### 阶段 4：收拢编剧与资产诊断规则

目标：吸收数值诊断，不复制第二套作者数据。

- 将 `novel-outline` 的预算、爽点间隔和角色/场景过载诊断改写为可选的开发期评估。
- 将 `novel-script` 的钩子位置、爽点认领、台词长度、发声时长和场次覆盖转成
  从 Markdown 可机械读出的检查；无法可靠解析的语义判断留给审查技能。
- 将 `novel-art` 的参考板约束限定到“生成参考板”范围，不限制所有画面必须无人、
  无手或纯白。
- 将 `novel-characters` 的多视图版面、身份锚点与语言分工吸收到图片提示词手艺文档。
- 所有阈值优先从 `short-drama.json` 的已接受档案读取；未接受时不触发数值失败。

验收：

- 同一份剧本在未配置项目阈值时不会因任意默认数字被误判失败。
- 项目声明语速、集长和目标模型后，相关检查才启用并给出可定位错误。
- 规则分级测试证明硬门只在声明范围内生效。

#### 阶段 5：吸收 Dashboard 与报告经验

目标：提高阅读和调整效率，不新增第二套项目页面。

- 在现有 Dashboard 的“分镜”阶段加入场景站位、人物位置、轴线和变化摘要。
- 可选加入可拖动俯视平面；保存动作仍只通过版本校验的 Markdown 保存路径，
  或由工具生成 Markdown 后走同一保存流程。
- 在“设定”阶段增加角色参考图版本、过期原因与模型来源摘要，不暴露密钥、哈希或
  内部协议状态。
- 在“提示词”阶段吸收生成批次、配音对齐和 H3/Seedance 差异视图。
- 报告导出优先复用现有 `export` 清单与 Dashboard 渲染，不复制 Shuohao 的单页报告框架。
- 4.3 的离线投产包属于分镜交付物，可从 Dashboard 查看和重新生成，但不在浏览器直接提交生成。

验收：

- 每个新增 server action 同时有单元测试和 HTTP 测试。
- 1440×900 与 390×844 无横向滚动、遮挡或控件溢出。
- Dashboard 仍只负责读取、编辑与请求复制，不在浏览器直接启动付费生产。

#### 阶段 6：兼容迁移与发布

目标：让已有 Shuohao 项目能迁移，又不把旧格式带入新主链。

- 在维护工具而非创作技能中提供一次性转换器：
  - `outline.json` → `项目开发/`；
  - `script.json` → 《剧本.md》；
  - `cast.json` / `art.json` → 《视觉设定.md》与《图片提示词.md》；
  - `staging.json` → 《分镜.md》的场景站位；
  - `storyboard.json` → 《分镜.md》与《视频提示词.md》。
- `asset.json` 与 PNG 元数据 → 参考图版本、父图关系和过期状态。
- 转换器把无法无损映射的字段写到 `项目开发/迁移待决.md`，不替用户猜创作决定。
- 迁移完成后，正式运行不再依赖旧 JSON。
- 更新 README、CHANGELOG、安装说明、示例和能力边界。
- 如果新增阶段与生产契约保持向后兼容，版本建议从 `0.9.2` 进入 `0.10.0`；
  如果必须破坏既有文档或 CLI 契约，再升级 `1.0.0`。

验收：

- 至少一份 Shuohao 合成项目可完整迁移并通过五文档检查。
- 迁移后删除旧 JSON，项目仍能渲染 Dashboard、生成视频提示词和导出交付包。
- 安装任意单个 Drama 技能时，不依赖旧仓库、Node 或其他兄弟技能。

### 6. 并行与依赖

阶段 2 与阶段 3 可以在阶段 1 契约稳定后并行：

- 阶段 2 主要修改 `short-drama-storyboard`、`creator_markdown_check.py` 和 Dashboard 分镜视图。
- 阶段 3 主要修改 `short-drama-produce`、`short-drama-image-prompts` 和生产适配器。

阶段 4 依赖阶段 1 的规则分级，但可以与阶段 2/3 的知识文档工作并行。
阶段 5 依赖阶段 2/3 的可读数据接口。阶段 6 必须等待前面各阶段冻结后再做完整迁移测试。

单人完成生产级合并的粗估为 8–10 个工程师周。第一阶段可只交付 Markdown 空间契约、
站位校验、锚点 job 和离线投产包，粗估 5–6 周；拖动编辑器与完整 Dashboard 交互放到后续
增量，但 4.1 和 4.2 的数据契约不能后补。

### 7. 总体验收门

每个合并 PR 至少要证明：

- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v` 通过；
- `ruff check --no-cache .` 通过；
- 改动 Python 脚本时在 Python 3.9 下限环境再跑一次；
- 技能 Markdown 相对链接仍解析在本技能目录内；
- 新增规则有击穿测试，不以“文档里出现某句话”代替行为；
- `creator_markdown_check.py --partial` 在只有部分文档时仍能工作；
- 五文档齐备时，新增站位、节拍、时长、参考图和方言检查均能给出文档定位；
- 生产路径始终需要本次 job 的明确确认；
- 参考图派生 job 不能绕过父锚点确认、父输出 SHA256 和自身确认；
- reference-only workspace 可以不创建剧集完成角色参考图；
- 离线投产包可以从正式 Markdown 重新生成，且不成为第二创作真相；
- 站位缓存删除后可以从正式文档重建；
- 迁移后不存在新的长期创作 JSON；
- Apache-2.0 许可证正文、来源清单与 NOTICE 完整；
- Dashboard 视觉改动完成桌面与窄屏截图检查。

发布候选另外需要：

- 一份从 Shuohao 样例迁移的端到端项目；
- 一份从零开始的 Drama 项目；
- 一次 H3 与一次 Seedance 的离线投产包核对；
- 一次 fake adapter 的参考图锚点、派生、过期、恢复与 reference-only 流程；
- 一次站位 Markdown 与编辑器往返、缓存删除重建测试；
- 一次固定快照的人工主工作流评估。

### 8. 当前实施进度

截至 2026-10-30，已完成第一批可独立验证的能力：

- 阶段 0：Shuohao 2.2.1 全量文件清单、Apache-2.0 许可证与 NOTICE 已进入主仓。
- 4.1：空间视图、人物位置、跨文档校验、开场走位和可失效缓存已实现；
  纯文字场景站位保持兼容。
- 4.2：reference-only workspace、锚点/派生 job、父输出 SHA256 校验和
  fake-adapter 端到端流程已实现；父图在确认后变化会阻止派生运行。
- 4.3：H3/Seedance 离线投产包已实现，包含分组时长、附件顺序、缺口清单和
  可重建 manifest。
- Shuohao JSON 一次性迁移器已实现：大纲、角色、美术、剧本、站位和分镜可生成
  Drama Markdown；可选复制真实分镜图，未提供图片时使用 `PLAN-START`。
- Dashboard 分镜页已加入俯视站位：场景物件、人物、朝向、群演和未在场人物
  均由正式 Markdown 派生，并支持拖动、姿态/朝向、群演与 Markdown 回写；
  桌面与 390×844 窄屏已有实跑记录。
- Dashboard 已加入剧集与 reference-only 项目的参考图版本视图。
- 图片适配器已加入 GPT Image 2 / Qwen Image 的 APIMart 异步任务与恢复路径，
  Qwen 同时保留 ComfyUI；GPT Image 已有真实参考图运行证据。
- 已加入逐块节拍覆盖、项目语速驱动的对白估时与非阻断资产诊断。

后续实现决定见
[真实图片异步任务、项目参考图版本与可编辑站位](../../implemented/architecture/2026-10-30-real-provider-staging-and-release-candidate.md)。
本提案保留 proposed 状态，表示总体吸收方案尚未全部验收，不表示上述能力尚未开发。

本轮审查修复：

- 全仓审查确认的保存冲突保护、站位草稿离开保护、参考图过期传播、
  节拍匹配、跨镜对白估时和 Dashboard 诊断消费问题均已修复；同时补齐独立技能的许可闭包与版本锁。
  实现决定见[审查缺口修复](../../implemented/bug-fix/2026-10-30-close-repository-audit-findings.md)，
  证据见[仓库审查与关闭记录](../../../../evaluations/repository-audit-2026-10-30.md)。
- 尚无本轮真实 Qwen、Linux/macOS 和独立人工主工作流证据；这些是已知验证范围，
  本轮仓库审查不继续执行这些外部验收。

## Alternatives considered

- **保持两个独立仓库，只做互相跳转**
  - 最强理由：迁移成本最低，两边原有用户不受影响。
  - 不用：没有解决双真相、双解析器和双维护成本，不算“吸收”。

- **以 Shuohao 为主，补 Drama 的 Dashboard 和生产能力**
  - 最强理由：Shuohao 的 JSON 契约和确定性质量门更整齐，便于机器处理。
  - 不用：需要重建项目路由、生产确认、剪辑、审查、交付和完整 Dashboard；
    同时会把 JSON 继续放在创作者必须维护的位置。

- **把 Shuohao 代码原样复制，保留 Node 与 JSON**
  - 最强理由：已有 selftest 和成熟工具可以直接运行，短期交付快。
  - 不用：形成双运行时和双契约；Drama 的单技能自包含规则、Python 下限与
    creator-first 文档流都会被打穿。

- **只吸收文档与经验，不吸收确定性工具**
  - 最强理由：不触碰代码和数据格式，风险最低。
  - 不用：站位几何、锚点派生、节拍覆盖、时长对账和 H3 切点校验正是对方最有价值的部分；
    只抄文档无法复用其实际收益。

## Consequences

### 收益

- 创作者继续使用一套 Markdown 项目，不需要在 JSON 作者模式和文档模式之间切换。
- Drama Skills 获得更强的多人站位、机器质量门、锚点参考图和多协议投产能力。
- 规则、示例、Dashboard、生产与交付集中到一个仓库维护。
- Shuohao 的工具逻辑通过 Python 与统一确认边界进入现有生产体系，减少两套状态漂移。

### 代价

- 不是一次简单目录拷贝，需要逐项移植、改写和重测。
- 现有 Shuohao 项目需要一次性迁移工具，旧自定义脚本需要适配。
- Python 化会增加短期开发量，但避免长期维护第二运行时。
- 参考图生成会扩大生产技能的责任面，必须继续用外部 adapter、明确确认和审计记录隔离风险。
- Dashboard 增加编辑器后，测试范围会明显扩大。

### 风险与控制

- **双真相回潮**：任何新增 JSON 都必须说明是否派生、是否临时、是否可删除。
- **规则冲突**：供应商时长、题材阈值和视觉偏好不得直接升级为全局硬门。
- **许可证遗漏**：所有移植文件先登记来源，再进入公共技能目录。
- **旧格式绑定**：迁移器只能是一次性维护工具，不能让运行时重新依赖旧 schema。
- **生产误触**：任何生成、重试、续接或恢复行为都必须保持现有显式确认边界。
