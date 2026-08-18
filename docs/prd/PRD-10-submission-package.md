# PRD-10：提交打包

> **状态：🟡 基本完成** —— 英文 README（含架构图）、LICENSE（MIT）、Devpost 表单文案
> （`docs/07-devpost-submission.md`）均已完成。剩两项做不了：**演示视频**（需要真实录屏/上传
> YouTube，超出代码/文档能力范围）、**functional demo app 的可访问 URL**（需要真实部署）。
> 详见 `docs/07-devpost-submission.md` 顶部的提交清单核对。

## 目标

把前面 10 个 PRD 的成果打包成符合 Devpost 提交要求、且最大化评委印象分的最终材料。这一步的质量直接决定评委第一印象，不能压缩时间敷衍。

## 范围

- 英文 README（仓库根目录）
- LICENSE（MIT，需在仓库 About 区域可见）
- 架构图
- <3 分钟演示视频（YouTube/Vimeo 公开）
- CockroachDB / AWS 工具使用说明（Devpost 表单要填的内容）
- 提交清单逐项核对

## 非目标

- 不做多语言 README（英文优先，中文方案文档留在 `docs/` 目录供团队内部使用即可）

## 功能需求

1. **英文 README** 需包含：
   - 项目一句话定位 + 解决的问题
   - 架构图 + 简要说明
   - Setup / Run 说明（能让评委在本地或云上跑起来）
   - CockroachDB 工具使用清单：MCP Server / Distributed Vector Indexing / ccloud CLI（+ Agent Skills 如已做）分别用在哪、做了什么
   - AWS 服务使用清单：Bedrock、Lambda（+ S3/CloudWatch/SNS/Secrets Manager 等）分别用在哪、做了什么
   - Demo app 链接、视频链接
2. **LICENSE**：MIT，放仓库根目录，确认 GitHub About 区域能自动识别显示
3. **架构图**：基于 `docs/01-architecture.md` 第 2 节画出组件图（draw.io 或 mermaid），突出"CockroachDB 作为记忆层"这个核心叙事，而不是画成普通的服务拓扑图
4. **演示视频（<3 分钟）**：
   - 开头 15 秒：一句话讲清楚项目是什么、解决什么问题
   - 中段：基于 PRD-08 演示剧本，选 1-2 个场景现场展示"攻击 → AI 判定 → 自动拉黑 → 网关拒绝"完整闭环
   - **必须有一段专门展示 Dashboard 的记忆时间线视图**，讲清楚"CockroachDB 不是日志盘，是 agent 会读会用的记忆"，这是评委评分表上明确写的"CockroachDB 记忆层实际生效"
   - 结尾：简要提及生产就绪的设计（最小权限、双层防护）
   - 上传 YouTube 或 Vimeo，设为公开
5. **Devpost 提交表单内容**：逐项对照"用到的 CockroachDB 工具/AWS 服务及具体用途"提前写好文案，避免临交前现想
6. 可选：写一段对 CockroachDB AI 工具的真实使用反馈（友好加分项，不需要刻意吹捧，客观反馈即可）

## 用到的 CockroachDB & AWS 工具

无新增，本 PRD 是对前面所有工具使用的**文档化和证据打包**。

## 验收标准

对照以下清单逐项打勾（与 `docs/01-architecture.md` 第 6 节一致）：

- [ ] 公开开源仓库 + README（含 setup/run 说明）+ LICENSE（MIT，仓库 About 区域可见）
- [ ] 可访问的 functional demo app URL
- [ ] <3 分钟视频，YouTube/Vimeo 公开，展示 CockroachDB 记忆层实际生效
- [ ] 明确写出用到的 CockroachDB 工具及具体用途
- [ ] 明确写出用到的 AWS 服务及具体用途
- [ ] 架构图
- [ ] （可选）CockroachDB AI 工具反馈

## 负责人

Person B 主导（README、视频剪辑、提交表单），Person A 协助（架构图技术准确性 review、工具使用说明的技术细节）

## 预估工作量

2 天

## 依赖

所有前置 PRD 完成（这是最后一步，Week 3 后半段）
