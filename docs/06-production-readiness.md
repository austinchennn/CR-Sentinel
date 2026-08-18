# 生产就绪加固 / Production Readiness（PRD-09 剩余部分）

对应 `docs/prd/PRD-09-observability-hardening.md`。重试/降级处理已经在 PRD-03/04 里实现（见该
PRD 文档的状态行），这份文档覆盖剩下的四项：IAM 最小权限、凭证管理确认、CloudWatch、幂等性复查，
以及双层防护说明的索引。

## 1. IAM 最小权限清单

逐条检查了三个部署为 Lambda 的服务（`crdb-schema` 只是迁移脚本，不部署 Lambda，不在此列）：

| 服务 | 函数 | 权限 | 为什么需要 |
|---|---|---|---|
| demo-target-app | 全部 4 个（Login/Profile/Comments/Admin） | 无自定义 `Policies:`（仅 SAM 默认的 `AWSLambdaBasicExecutionRole` 等价权限：写 CloudWatch Logs） | 这四个函数只通过 psycopg2（网络层，不经 IAM）访问 CRDB，不调用任何其他 AWS API — 本来就不需要任何自定义 IAM 权限，模板里从未加过，检查后确认无需改动 |
| dashboard | 全部 3 个（Logs/Blacklist/Episodes） | 同上，无自定义 `Policies:` | 只读查询 CRDB，同样不调用其他 AWS API |
| patrol-agent | PatrolAgentFunction | `bedrock:Converse`，`Resource` 限定到 `${BedrockModelId}` 这一个 foundation model ARN | `BedrockJudge.judge()` 调用 Converse API，只需要这一个模型 |
| patrol-agent | PatrolAgentFunction | `bedrock:InvokeModel`，`Resource` 限定到 `amazon.titan-embed-text-v2:0` 这一个 foundation model ARN | `embeddings.embed_text()` 调用 InvokeModel，只需要 Titan 这一个模型 |
| patrol-agent | PatrolAgentFunction | `sns:Publish`，`Resource` 限定到 `AlertTopic` 这一个 Topic | `_publish_alert()` 只发布到这一个 Topic |
| patrol-agent | PatrolAgentFunction | `cloudwatch:PutMetricData`，`Resource: "*"` | `CloudWatchMetrics.publish_round_summary()` 需要；`PutMetricData` 是 AWS IAM 里为数不多**不支持资源级权限**的 action（见 AWS Service Authorization Reference），`"*"` 已经是这个 action 能收紧到的极限，不是遗漏 |

改动：`services/patrol-agent/template.yaml` 里 Bedrock 的两条权限原来是一条 `Resource: "*"`
（覆盖账号里所有 foundation model），现在拆成两条、各自限定到实际用到的模型 ARN。

## 2. 凭证管理确认

全仓库搜索了 `password\s*=\s*['"]...`、`secret`、`api[_-]?key` 等模式的硬编码赋值（排除测试
fixture、`WEAK_CREDENTIALS`——demo 靶场故意的弱密码数据不算凭证泄露、`NoEcho`/占位符/生成密码
的注释），**没有发现任何硬编码密钥或连接串**。全部凭证都通过环境变量注入（`CRDB_*`/`MCP_API_KEY`/
`CRDB_WRITE_*`/`CRDB_DASHBOARD_*`），`template.yaml` 里全部标了 `NoEcho: true`，实际值预期来自
Secrets Manager（PRD-00 部署时注入，仓库里从不出现明文）。

## 3. CloudWatch

新增（`services/patrol-agent/patrol_agent/metrics.py` + `template.yaml`）：

- **自定义指标**（namespace `CRSentinel/PatrolAgent`）：`LogsRead`、`SuspiciousIpCount`、
  `HighRiskVerdicts`、`LowRiskVerdicts`、`RoundDegraded`，每轮巡检结束后发布一次
  （`app.py::patrol_handler` 里，`try/except` 单独包裹——指标发布失败不能影响巡检本身已经产生的
  处置结果，同样的隔离原则见 PRD-06 alerting 的 `_publish_alert`）。
- **Alarm**：`FunctionErrorAlarm`（Lambda 未捕获异常）、`RoundDegradedAlarm`（连续 3 轮
  `RoundDegraded >= 1`，即 MCP 连续 3 轮不可达）。
- **Dashboard**：`PatrolAgentDashboard`，四个面板——Lambda 调用/错误数、Lambda 耗时、巡检轮次
  自定义指标、降级轮次趋势。部署后从 `PatrolAgentDashboardUrl` 输出直接打开。

测试：`services/patrol-agent/tests/test_metrics.py`（`CloudWatchMetrics.publish_round_summary`
对不同 `RoundSummary` 输入的指标计算），以及扩展了
`tests/patrol-agent/conftest.py` 的 fake boto3 客户端支持 `put_metric_data`，避免
之前已经出现过一次的"新增必需调用但覆盖率测试套件没跟上"回归（见 PRD-06 合并后修的那次
`SNS_TOPIC_ARN` 缺失问题）。

## 4. 幂等性复查

逐个检查 `write_client.py` 六个处置写入方法：

| 方法 | 幂等机制 | 结论 |
|---|---|---|
| `write_blacklist` | `INSERT ... ON CONFLICT (ip) DO UPDATE` | 幂等：重复判定同一 IP 为 high，只会更新已有行，不会重复 |
| `write_rate_limit` | 同上，`ON CONFLICT (ip) DO UPDATE` | 幂等 |
| `lock_account` | 纯 `UPDATE ... WHERE user_id = %s` | 天然幂等（重复执行终态相同） |
| `write_episode` | **无**——每次 `INSERT`，`id` 是随机 `gen_random_uuid()` | **不幂等**，见下方"已知限制" |
| `write_task` | 同上，纯 `INSERT` | 同上（PRD-09 验收标准没有明确要求这条，但风险类别相同） |
| `write_alert` | 同上，纯 `INSERT`；`sent` 字段本身是给"是否已推送"做幂等标记的，不是给"是否已写入"做幂等 | 同上 |

### 已知限制：Lambda 重试可能导致 `agent_episodes`（以及 `task_queue`/`alert_log`）重复写入

PRD-09 验收标准 5 明确要求"重复触发同一轮巡检...`agent_episodes` 不产生重复/冲突记录"。目前
`write_episode`/`write_task`/`write_alert` 都是无约束的 `INSERT`，如果 EventBridge Scheduler
在一次 Lambda 调用超时/报错后重试整个 `patrol_handler`（`template.yaml` 的 `PatrolSchedule`
没有显式关闭 `RetryPolicy`，走的是 EventBridge Scheduler 默认重试行为），且重试发生在上一次已经
成功写完处置动作 **之后**，会产生重复的 `agent_episodes`/`task_queue`/`alert_log` 行。

**为什么没有直接修**：`ip_blacklist`/`ip_rate_limit` 能用 `ON CONFLICT (ip)` 幂等，是因为"同一个
IP 只应该有一条生效记录"本身就是业务语义。但 `agent_episodes` 恰恰相反——**同一个 IP 在不同轮次
产生多条不同记录，是这个项目最核心的"记忆时间线"叙事**（Dashboard 记忆时间线视图整个存在的意义）。
如果用 `(ip, risk_level, attack_type, reasoning_summary)` 之类的内容做 `ON CONFLICT` 去重，会把
"同一个 IP 连续两轮都判定为 high/sqli"这种合法的、应该被记录两次的场景，错误地合并成一条记录并
覆盖时间戳——这比偶发的重试重复更糟，等于破坏了记忆时间线本身。

真正正确的修法需要一个能跨重试保持稳定的幂等键（比如"这一轮巡检读到的 `request_logs.id` 集合的
哈希"），但 `read_recent_logs` 用的是"过去 N 分钟"这种滑动窗口（`WHERE ts > now() - INTERVAL`），
每次调用的 `now()` 都不同，两次重试实际读到的日志集合不保证完全一致，无法简单地用固定 key 去重。
这是一个需要专门设计（比如引入显式的"巡检轮次" ID，由 EventBridge 传入或由 Lambda 自己生成并在
重试间保持）的问题，不是加一个 `ON CONFLICT` 能解决的，超出这次加固的时间范围。

**建议**：如果要正式解决，下一步是给 `patrol_handler` 加一层"本轮是否已处理过"的检查（比如在
`agent_episodes` 加一个 `round_id` 列，`patrol_handler` 从 EventBridge 事件里取一个稳定的调用
标识符，重试时复用同一个 `round_id`，`write_episode` 改成 `ON CONFLICT (round_id, ip) DO NOTHING`）。
记入 `docs/04-todo.md`。

## 5. 双层防护说明

已经在 `docs/01-architecture.md` 第 2.5 节和"已知短板与折中"表里写清楚："网关层（PRD-05 的
`gated` 中间件）做毫秒级即时拦截，AI 巡检做深度事后判定和高级入侵识别，两层配合应对 5 分钟批量
巡检的实时性短板"——这是 PRD-09 功能需求 6 要求的内容，之前就已经完成，这里不重复。
