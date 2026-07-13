# PRD-09：可观测性 & 生产就绪加固

## 目标

把项目从"能跑的 demo"补齐到"体现生产思考"的程度，直接对应 Production Readiness 评分项：安全性、可观测性、可扩展性、失败处理。这一步不是锦上添花，是评委明确会打分的项目。

## 范围

- IAM 权限收紧到最小必要集
- 全部凭证从 Secrets Manager 读取，代码里无硬编码
- CloudWatch 指标/日志/告警看板
- 关键路径的重试/超时/降级处理
- 幂等性复查
- （可选）ccloud CLI 审计日志展示、Agent Skills 使用说明

## 非目标

- 不做多区域容灾（时间不允许，但可以在 README 里说明 CockroachDB 本身的分布式特性天然支持这个扩展方向）
- 不做完整的渗透测试/合规认证

## 功能需求

1. **IAM 最小权限**：逐条检查 `PatrolAgentLambda`、靶场应用 Lambda、Dashboard 只读 API 的执行角色，去掉一切非必要权限（例如靶场应用不该有 Bedrock 调用权限，只读 API 不该有写权限）
2. **凭证管理**：全面排查代码库，确认没有任何硬编码的 CRDB 连接串/AWS 密钥，全部走 Secrets Manager + IAM role
3. **CloudWatch**：
   - Lambda 执行错误率、耗时的基础指标看板
   - 巡检轮次的自定义指标（本轮处理日志数、判定为 high 的数量）
   - 关键错误（MCP 连接失败、Bedrock 调用失败）配置 CloudWatch Alarm
4. **失败处理**：
   - MCP/Bedrock/CRDB 写入任一环节失败时，不产生半成品数据（宁可整轮跳过，不要写入不完整的处置记录）
   - 关键外部调用（Bedrock、MCP）加超时和有限重试
5. **幂等性复查**：确认 PRD-05 的写入操作在网络重试、Lambda 重复触发等场景下不会产生脏数据
6. **双层防护说明**：在文档里明确写清楚"网关即时拦截 + AI 深度巡检"如何应对"5 分钟延迟"这个已知短板，这是主动暴露短板并给出合理折中，比藏着不说更能体现工程成熟度
7. （可选，时间富余再做）ccloud CLI 拉取集群审计日志，展示在 Dashboard 或截图放入提交材料；整理一段"我们如何使用 CockroachDB Agent Skills 辅助 schema 设计"的说明

## 用到的 CockroachDB & AWS 工具

- **CockroachDB**：ccloud CLI（审计日志，可选项）
- **AWS**：IAM、Secrets Manager、CloudWatch（Logs、Metrics、Alarms）

## 验收标准

- [ ] 代码库全文搜索无硬编码密钥/连接串
- [ ] 每个 Lambda 角色的权限清单逐条能说清楚"为什么需要这条权限"
- [ ] CloudWatch 能看到巡检轮次的自定义指标曲线
- [ ] 故意让 Bedrock 调用超时/失败一次，验证 Lambda 优雅降级、不产生脏数据、有清晰错误日志
- [ ] 重复触发同一轮巡检（模拟 Lambda 重试），`ip_blacklist`/`agent_episodes` 不产生重复/冲突记录

## 负责人

A + B 共同

## 预估工作量

2 天

## 依赖

PRD-04、PRD-05（核心功能已跑通，这一步是加固而非新功能）
