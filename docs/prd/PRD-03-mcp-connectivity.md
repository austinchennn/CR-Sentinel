# PRD-03：MCP 连接层

## 目标

封装 PatrolAgentLambda 与 CockroachDB 之间的两条通道：MCP（只读，日志查询 + 向量检索）和独立的最小权限 SQL 写入通道（处置动作）。这一层是"正确、安全地使用 CockroachDB 工具"这个评分点的直接体现，也是全项目里唯一需要格外小心权限边界的模块。

## 范围

- MCP client 封装：连接 CockroachDB Cloud Managed MCP Server（只读模式），暴露给上层的"读日志"和"语义检索"两个方法
- 独立写入 client：用 Secrets Manager 里的最小权限凭证，直连 CRDB 执行 INSERT/UPDATE（不经过 MCP）
- 错误处理：MCP 连接失败、超时的降级策略（不能让巡检整轮挂掉）

## 非目标

- 不包含 Bedrock 调用逻辑（见 PRD-04）
- 不包含具体处置动作的业务规则（见 PRD-05）

## 功能需求

1. 用 CockroachDB Cloud Console 生成的 MCP 配置片段接入（`https://cockroachlabs.cloud/mcp`），验证只读模式下可执行的工具集
2. 封装"读最近 N 分钟日志"方法：内部调用 MCP 的读查询工具
3. 封装"语义检索"方法：给定一段文本/embedding，调用 MCP 的向量检索工具，从 `attack_signatures` 召回相似攻击特征
4. 封装"读某 IP 历史记忆"方法：从 `agent_episodes` 查该 IP 过去的判定记录（可以走 MCP 只读，也可以走同一只读连接）
5. 独立写入 client：使用与 MCP 完全不同的凭证（来自 Secrets Manager，仅授予对处置相关表的 INSERT/UPDATE 权限），封装"写黑名单"、"写限流"、"锁账号"、"写记忆"、"写任务队列"、"写告警"六个方法
6. 任一通道失败时要有清晰日志和降级（例如 MCP 超时就跳过本轮，不写入任何半成品数据，保证幂等和可重试）

## 用到的 CockroachDB & AWS 工具

- **CockroachDB**：MCP Server（只读，核心）、Distributed Vector Indexing（通过 MCP 的语义检索）
- **AWS**：Secrets Manager（写入通道凭证）、Lambda（宿主环境）

## 验收标准

- [ ] 能通过 MCP 只读连接成功查询 `request_logs`，且用只读凭证尝试写入会被拒绝（验证权限边界真实生效，不是摆设）
- [ ] 语义检索方法对一段"变形 SQL 注入"文本能召回 `attack_signatures` 里相关的 sqli 特征
- [ ] 独立写入 client 成功写入一条测试黑名单记录，且该凭证对非白名单表（如 `request_logs`）没有写权限
- [ ] MCP 连接故意断开时，巡检流程能优雅降级并记录日志，不抛未捕获异常

## 负责人

Person A

## 预估工作量

1.5 天

## 依赖

PRD-00（Secrets Manager 已就绪）、PRD-01（表结构已就绪）
