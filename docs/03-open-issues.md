# Open Issues / 待决问题

这份文档记录 2026-08-11 代码审查（覆盖 `services/crdb-schema`、`services/demo-target-app`、`services/patrol-agent` 三个服务的全部业务代码）中发现、且已经处理或仍待决策的问题。

## 已修复的 bug

### 1. `demo_target_app/http.py` `source_ip()` 在 `headers` 为 `None` 时崩溃

`event.get("headers", {})` 只有在 `event` 里**完全没有** `headers` 这个 key 时才会返回默认值 `{}`；如果 API Gateway 传来的事件里 `headers` 这个 key 存在但值是 `None`（真实事件在没有自定义 header 时会出现这种情况），`.get()` 拿到的就是 `None`，再调用 `.get("X-Forwarded-For", ...)` 会直接抛 `AttributeError`，导致整个请求（包括本该记录到 `request_logs` 的日志)崩掉。

同文件里的 `user_agent()` 已经用 `event.get("headers") or {}` 正确处理了这个情况，`source_ip()` 少写了这个 `or {}`，是明显的不一致。

**修复**：`services/demo_target_app/http.py`，`source_ip()` 改为先 `headers = event.get("headers") or {}` 再取值，和 `user_agent()` 保持一致。

### 2. 高危判定时，如果 episode embedding 失败，处置动作和告警会被一起跳过（已解耦）

`patrol_agent/patrol_loop.py` 的 `_dispatch_verdict()` 原来是先算 `episode_embedding`，失败就直接 `return`，导致黑名单/限流/锁账号/告警全部被跳过。已按本文档之前记录的方案实现：把处置动作 + 告警的执行挪到一个独立的 `try/except CrdbWriteError` 块里，`episode_embedding` 的计算和 `write_episode` 调用拆到新的 `_write_episode()` 函数，单独用 `try/except` 包裹。现在 embedding 失败只会跳过 `agent_episodes` 这一条记忆记录，不影响已确认的 `high` 风险判定的实际拦截和告警。新增测试：`test_high_verdict_episode_embedding_failure_does_not_block_disposal_or_alert`、`test_disposal_write_failure_does_not_block_episode_write`（`services/patrol-agent/tests/test_patrol_loop.py`）。

### 4. `patrol_agent/embeddings.py` 与 `crdb_schema/titan_embeddings.py` 手动重复、无一致性防护（已加测试守卫）

两份文件是刻意的字节级复制（各服务独立部署为 Lambda，见两个模块的 docstring），`MODEL_ID`/`EMBEDDING_DIMENSIONS` 必须保持一致，否则向量召回质量会静默下降。之前只有代码注释提醒，没有自动检测。已加 `services/patrol-agent/tests/test_embeddings_consistency.py`：把 `services/crdb-schema` 插进 `sys.path`，直接比较两边的 `MODEL_ID`/`EMBEDDING_DIMENSIONS`，任一改动导致不一致会立刻在 `patrol-agent` 测试套件里报错。

### 3. `accounts.username` 没有唯一约束（已加索引）

`migrations/001_core_tables.sql` 里 `accounts` 表只有 `user_id` 是主键，`username` 没有唯一索引/约束，`db.py` 的 `get_account_by_username` 却假设唯一。已加 `migrations/002_accounts_username_unique.sql`：`CREATE UNIQUE INDEX IF NOT EXISTS accounts_username_key ON accounts (username);`，独立迁移文件，不改动已跑过的 001。新增测试确认种子数据（`seed_accounts.py`）里没有重复用户名，迁移可以安全应用（`services/crdb-schema/tests/test_migration_accounts_username_unique.py`）。

## 待决问题（需要你确认，未擅自改动逻辑）

### 1. `BedrockConfig.model_id` 的默认值是占位符

`patrol_agent/config.py`:

```python
model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
```

代码注释里已经写明"override once the actual approved model ID is known rather than assuming this one is granted"——也就是说这个默认值本身就是待确认项，取决于 PRD-00 里 Bedrock 模型访问审批实际批下来的是哪个模型。部署前需要确认并通过 `BEDROCK_MODEL_ID` 环境变量覆盖（如果批下来的不是这个 ID）。

### 2. PRD-00（Infra & 账号 Bootstrap）没有对应的实现 commit

`git log` 里 PRD-01 到 PRD-05 都能各自对应到一个 feature commit，但 PRD-00（AWS/CockroachDB Cloud 账号、IAM、IaC 骨架、Bedrock 模型访问审批）没有找到对应的仓库改动——这类工作大概率是账号配置/控制台操作,不体现为代码提交,所以无法仅从代码库判断它是否已经完成。已在 `docs/prd/` 里保留未标记状态,具体是否完成需要你确认(见下方"PRD 完成情况"章节)。

## 复核过、判断为"设计如此、不是 bug"的地方

- `demo_target_app/handlers/profile.py`（IDOR）、`login.py`(弱口令)、`comments.py`(无过滤回显)、`admin.py`(无鉴权)——这四个端点的"漏洞"都是 PRD-02 明确要求的靶场攻击面,不是缺陷。
- `middleware.py` 的 `logged` 在 handler 抛异常时会先把 `response` 设为 500 再重新 `raise`——这是为了让 `finally` 里的 `repo.log_request()` 能拿到一个非 `None` 的 response 用于记录 `status_code=500`,同时仍然把异常继续抛给 Lambda 运行时。是刻意设计,不是遗漏的 `except` 块。
