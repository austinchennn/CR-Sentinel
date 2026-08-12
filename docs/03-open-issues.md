# Open Issues / 待决问题

这份文档记录 2026-08-11 代码审查（覆盖 `services/crdb-schema`、`services/demo-target-app`、`services/patrol-agent` 三个服务的全部业务代码）中发现、且已经处理或仍待决策的问题。

## 已修复的 bug

### 1. `demo_target_app/http.py` `source_ip()` 在 `headers` 为 `None` 时崩溃

`event.get("headers", {})` 只有在 `event` 里**完全没有** `headers` 这个 key 时才会返回默认值 `{}`；如果 API Gateway 传来的事件里 `headers` 这个 key 存在但值是 `None`（真实事件在没有自定义 header 时会出现这种情况），`.get()` 拿到的就是 `None`，再调用 `.get("X-Forwarded-For", ...)` 会直接抛 `AttributeError`，导致整个请求（包括本该记录到 `request_logs` 的日志)崩掉。

同文件里的 `user_agent()` 已经用 `event.get("headers") or {}` 正确处理了这个情况，`source_ip()` 少写了这个 `or {}`，是明显的不一致。

**修复**：`services/demo_target_app/http.py`，`source_ip()` 改为先 `headers = event.get("headers") or {}` 再取值，和 `user_agent()` 保持一致。

## 待决问题（需要你确认，未擅自改动逻辑）

### 1. 高危判定时，如果 episode embedding 失败，处置动作和告警会被一起跳过

`patrol_agent/patrol_loop.py` 的 `_dispatch_verdict()`：

```python
try:
    episode_embedding = embed_fn(verdict.reasoning or verdict.attack_type or verdict.ip)
except Exception as exc:
    logger.warning(...)
    return   # <- 直接整体返回，disposal 和 alert 都不会执行
```

如果 Titan embedding 调用失败（比如限流、瞬时网络问题），即使这一轮 Claude 已经判定某 IP 是 `high` 风险，**黑名单/限流/锁账号等实际防御动作、以及告警，都不会执行**——只是被跳过并打一条 warning 日志。

这符合 `patrol_loop.py` 模块注释里引用的 PRD-09 设计原则("宁可整轮跳过该项，不要写入不完整的处置记录")，看起来是刻意的"要么完整写入、要么完全不写"取舍，不是随手写错的判断。但从"这是一个自动防御产品"的角度看，让一次不相关的 embedding 服务抖动导致一次已确认的高危攻击完全不被拦截，是有实际风险的取舍。

**需要你决定**：是否要把处置动作/告警和 episode 记忆写入解耦，让 embedding 失败只影响 `agent_episodes` 这一条记忆记录，不影响黑名单/限流/告警？如果要改，我可以直接实现（把 `episode_embedding` 的计算挪到 disposal action 之后，用 `try/except` 单独包裹，仅影响 `write_episode` 调用）。目前没有改动这块逻辑,因为这是一个产品行为决策，不是纯粹的代码缺陷。

### 2. `BedrockConfig.model_id` 的默认值是占位符

`patrol_agent/config.py`:

```python
model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
```

代码注释里已经写明"override once the actual approved model ID is known rather than assuming this one is granted"——也就是说这个默认值本身就是待确认项，取决于 PRD-00 里 Bedrock 模型访问审批实际批下来的是哪个模型。部署前需要确认并通过 `BEDROCK_MODEL_ID` 环境变量覆盖（如果批下来的不是这个 ID）。

### 3. `accounts.username` 没有唯一约束

`migrations/001_core_tables.sql` 里 `accounts` 表只有 `user_id` 是主键，`username` 没有唯一索引/约束。`db.py` 的 `get_account_by_username` 假设 username 唯一（`fetchone()` 只取第一条），种子数据（`seed_accounts.py`）里也确实没有重复用户名，但 schema 层面没有强制这一点。如果未来有非种子途径写入 `accounts`（比如注册流程),没有唯一约束会导致登录时随机拿到某一个同名账号。当前 demo 范围内不影响功能，是否需要加唯一索引取决于 `accounts` 表未来是否会有除种子脚本外的写入路径。

### 4. PRD-00（Infra & 账号 Bootstrap）没有对应的实现 commit

`git log` 里 PRD-01 到 PRD-05 都能各自对应到一个 feature commit，但 PRD-00（AWS/CockroachDB Cloud 账号、IAM、IaC 骨架、Bedrock 模型访问审批）没有找到对应的仓库改动——这类工作大概率是账号配置/控制台操作,不体现为代码提交,所以无法仅从代码库判断它是否已经完成。已在 `docs/prd/` 里保留未标记状态,具体是否完成需要你确认(见下方"PRD 完成情况"章节)。

## 复核过、判断为"设计如此、不是 bug"的地方

- `demo_target_app/handlers/profile.py`（IDOR）、`login.py`(弱口令)、`comments.py`(无过滤回显)、`admin.py`(无鉴权)——这四个端点的"漏洞"都是 PRD-02 明确要求的靶场攻击面,不是缺陷。
- `middleware.py` 的 `logged` 在 handler 抛异常时会先把 `response` 设为 500 再重新 `raise`——这是为了让 `finally` 里的 `repo.log_request()` 能拿到一个非 `None` 的 response 用于记录 `status_code=500`,同时仍然把异常继续抛给 Lambda 运行时。是刻意设计,不是遗漏的 `except` 块。
