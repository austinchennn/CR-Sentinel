# PRD-04：Patrol Agent（Bedrock 推理循环）

> **状态：✅ 已完成**（D10 链式入侵关联分析的"加强项"未做）—— `services/patrol-agent`（commit `6874462`）。

## 目标

实现整个项目的"大脑"：EventBridge 定时触发的 Lambda，读日志 + 召回记忆 → 组装 prompt → Bedrock Claude 结构化推理 → 输出处置指令。这是全项目工作量最大、也是评委最关注的模块（Agentic Memory Design + Technical Implementation 两项评分的核心证据都在这里）。

## 范围

- EventBridge Scheduler 配置（每 2-5 分钟触发）
- PatrolAgentLambda 主流程编排
- Prompt 组装逻辑：日志 + 向量召回的攻击特征 + 该 IP 历史记忆
- Bedrock Claude tool-use 调用，解析结构化输出
- 结果分支逻辑（normal/low/high）

## 非目标

- 不包含具体处置动作的写入实现（复用 PRD-03 封装的写入 client，写入的业务规则细节见 PRD-05）
- 不包含跨请求链式入侵的复杂关联分析（先做单轮基础版，链式场景作为 Week 2 D10 的加强项）

## 功能需求

1. EventBridge 规则：每 2-5 分钟触发一次 `PatrolAgentLambda`（时间间隔可配置，demo 时可以调短以加快演示节奏）
2. 主流程：
   - 通过 PRD-03 封装的方法读近 N 分钟 `request_logs`
   - 对可疑请求（简单启发式预筛，如异常状态码、含特殊字符参数、高频 IP）做向量语义检索，召回相关 `attack_signatures`
   - 读该 IP 在 `agent_episodes` 中的历史记忆（是否是常客、之前判定过什么）
   - 组装 prompt：包含原始日志片段、召回的攻击特征描述、该 IP 历史记忆摘要、静态业务规则说明
3. 调用 Bedrock Claude（tool use / function calling），强制输出结构化 JSON：`{ip, risk_level, attack_type, action, reasoning}`
4. 按 `risk_level` 分支：
   - `normal`：不写入，结束
   - `low`：调用 PRD-03 写入 client 记一条 `agent_episodes`（不处置）
   - `high`：调用处置动作（见 PRD-05）+ 写 `agent_episodes` + 写 `alert_log`
5. 整轮巡检的关键节点（读到多少日志、召回了什么、Claude 输出了什么）打到 CloudWatch 日志，方便 demo 时展示"agent 在想什么"

## 用到的 CockroachDB & AWS 工具

- **CockroachDB**：MCP Server（只读）、Distributed Vector Indexing（语义召回）
- **AWS**：Lambda、EventBridge Scheduler、Bedrock（Claude tool use + Titan Embeddings 生成 query embedding）

## 验收标准

- [ ] EventBridge 能按配置间隔稳定触发 Lambda
- [ ] 单次巡检能完整跑完"读日志 → 召回 → 组装 prompt → Bedrock 判定"全流程且不报错
- [ ] Bedrock 输出稳定符合结构化 schema（跑 10 次不同输入，输出格式无解析失败）
- [ ] **核心验收（对应 Agentic Memory Design 的实证）**：连续两轮巡检中，同一 IP 第二次被判定时，能在 CloudWatch 日志里看到 prompt 里包含了第一轮 `agent_episodes` 的记忆摘要，且 Claude 的推理引用了这段历史（例如"该 IP 此前已被记录为可疑扫描行为，本次进一步升级判定为高危"）
- [ ] normal/low/high 三种分支都能被正确触发和处理

## 负责人

Person A

## 预估工作量

3 天

## 依赖

PRD-01（schema 就绪）、PRD-03（MCP/写入通道就绪）
