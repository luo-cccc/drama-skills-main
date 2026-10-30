# Agent Note: 真实图片异步任务、项目参考图版本与可编辑站位

Status: implemented

## Problem

APIMart 的 GPT Image 2 与 Qwen Image 3.0 按异步任务返回：创建请求给出
`task_id`，完成结果在 `/v1/tasks/{task_id}` 的 `result.images[].url[]`。现有图片
适配器只接受 OpenAI 同步 `data[0].b64_json`，因此真实请求虽然提交成功，却无法
取回图片。参考图版本账本已经能记录 reference-only 输出，但 Dashboard 只从剧集
路径读取，独立参考图工作区没有可视化入口。结构化站位目前只读；创作者改站位仍
要手写 Markdown。

跨文档检查已经能证明场景 ID 被镜头引用，却没有证明每个剧本动作、对白与生产标签
都有镜头承载；也没有按项目已接受语速核对对白能否在声明镜长内说完。资产诊断同样
缺少只基于当前 Markdown 和已确认事实的确定性报告。

## Decision

- 图片适配器同时支持同步 OpenAI 响应、同步 URL、APIMart 提交任务与任务轮询。
  提交拿到任务 ID 后先落恢复句柄；collect 只轮询既有任务，不重新提交。
- GPT Image 的参考图传输显式区分 OpenAI multipart edit 与 APIMart JSON
  `image_urls`。Qwen 保留 ComfyUI 工作流，并增加 APIMart 异步 API 路径。
- Dashboard 增加项目级参考图版本读取，同时支持
  `剧集/<EP>/制作成果/references/index.json` 与 `production/reference/index.json`，
  继续以当前 Markdown、输出字节和父图 SHA-256 判断 current / expired。
- `creator_markdown_check.py` 从《剧本.md》派生动作、对白与可见生产标签块，
  要求每个块在当前《分镜.md》的来源、动作边界或声音中被承载。存在已接受
  `format.pacing` 时，按对白发声字数与匹配镜长报告不足；没有语速时不猜。
- 资产诊断只报告能从当前文件证明的未引用条目、空识别锚点和被提及但未入画的
  候选，作为 review 信息，不把题材默认值升级为全局硬门。
- Dashboard 的结构化站位支持指针拖动、姿态与朝向调整、群演数量和位置编辑。
  保存动作提交场景、当前位置和 `分镜.md` 版本；服务端验证对象与坐标后只替换
  对应站位块，不保存长期 JSON。
- 发布候选扩大多集、outline-only、CRLF、缺档和真实分镜图语料，并明确区分
  Windows 实跑、Python 3.9 实跑与未实跑平台。

## Alternatives considered

- **为 APIMart 另写一套完整 provider adapter**：能把同步与异步边界分开，但会
  重复凭证、URL、任务恢复、下载和媒体校验；在同一个图片适配器内区分返回形态
  能用更小的接口维持现有确认与审计流程。
- **仅支持 ComfyUI Qwen**：本地工作流可控，但用户提供的真实网关已提供
  Qwen Image 3.0，拒绝它会让参考图测试依赖本机 GPU 和模型文件。
- **把拖拽结果写入 `.short-drama/staging/*.json`**：编辑响应快，但会形成第二份
  可编辑真相；只在内存中编辑并在保存时回写 Markdown，删除缓存后不丢创作结果。
- **用默认语速和统一容差阻断**：实现简单，却会把题材差异伪装成项目事实；只在
  创作者已接受语速时计算，并如实报告估算边界。

## Consequences

真实网关的中断恢复和 URL 下载得到测试，但轮询配置与供应商任务状态会进入适配器
运维面。项目级参考图视图与剧集视图共享同一过期判定，代价是需要统一 manifest
读取路径。拖拽保存增加一个 Dashboard server action 和版本冲突测试，换来创作者
不需要手改坐标。节拍覆盖会暴露旧项目的真实遗漏，因此发布前需要更新过时样例或
明确未拍场次。资产诊断保持非阻断，自动化只能提示可证事实，语义资产判断仍归审查。
