# PRD-05：自动处置动作 + 网关拦截

## 目标

完成"检测 → 处置 → 拦截"的闭环最后一环：AI 判定高危后，自动写入黑名单/限流/锁账号，且靶场应用的 API Gateway 层要真正读这些表并拒绝请求。这是证明 CR-Sentinel 不只是"发现"而是"发现 + 自动执行防御"的关键 PRD。

## 范围

- 处置动作的业务规则实现（在 PRD-03 写入 client 基础上）
- API Gateway 前置拦截逻辑：查 `ip_blacklist`/`ip_rate_limit`
- 处置动作的幂等性（同一 IP 重复判定不产生脏数据）

## 非目标

- 不包含告警推送（见 PRD-06）
- 不包含 Dashboard 展示（见 PRD-07）

## 功能需求

1. 高危攻击（`risk_level = high`）→ 写 `ip_blacklist`：区分临时封禁（如 24 小时，`block_until` 设置）和永久封禁，具体时长/永久由 Claude 输出的 `action` 字段决定
2. 中危扫描/爬虫 → 写 `ip_rate_limit`：设置该 IP 的每分钟请求上限，不直接拒绝
3. 账号异常（异地登录、批量改密码等）→ 更新 `accounts`：`locked = true`、`locked_reason`、`force_logout_at`
4. 通用加固建议（如"发现频繁 SQL 注入 → 建议给接口加参数白名单"）→ 写 `task_queue`，状态 `pending`
5. 所有写入操作要幂等：同一 IP 短时间内重复判定为 high，不应重复插入冲突记录，而是更新已有记录（如延长封禁时间、更新原因）
6. API Gateway（或 Lambda authorizer / 靶场应用入口中间件）在处理每个请求前：
   - 查 `ip_blacklist`，命中且未过期 → 直接拒绝（403）
   - 查 `ip_rate_limit`，命中 → 按限流规则处理（超限拒绝，未超限放行）
   - 都未命中 → 正常放行，走 PRD-02 的业务逻辑

## 用到的 CockroachDB & AWS 工具

- **CockroachDB**：独立写入通道（处置动作写入）、直接读（网关拦截查询，走独立的只读路径，不占用 MCP 配额）
- **AWS**：Lambda、API Gateway

## 验收标准

- [ ] 用攻击模拟器（PRD-08）打一发慢速爆破，等一轮巡检后 `ip_blacklist` 出现该 IP 记录
- [ ] 该 IP 再次请求靶场任意端点，立即被 API Gateway 拒绝（403），无需等待下一轮巡检
- [ ] 中危扫描场景验证限流生效：超过 `limit_per_min` 后续请求被拒绝，未超过时正常放行
- [ ] 账号锁定场景验证：`accounts.locked = true` 后，该账号无法登录
- [ ] 连续两轮巡检同一 IP 都判定 high，`ip_blacklist` 表里该 IP 只有一条记录（验证幂等，无重复/冲突）

## 负责人

Person A（处置写入逻辑）+ Person B（网关拦截逻辑）

## 预估工作量

2 天

## 依赖

PRD-03（写入通道）、PRD-04（Bedrock 输出结构化处置指令）
