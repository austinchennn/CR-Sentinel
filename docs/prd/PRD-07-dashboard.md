# PRD-07：Security Ops Dashboard

## 目标

给评委一个"一眼看懂记忆在起作用"的界面。这是整个项目里对 Agentic Memory Design 评分项**视觉化举证**最直接的部分——文字描述记忆机制不如让评委亲眼看到 agent 引用历史记忆做出决策。

## 范围

- 静态前端（S3 + CloudFront 托管）
- 只读 Lambda API（供前端读 CRDB 数据）
- 三个核心视图：实时日志流、黑名单/限流状态、agent 记忆时间线

## 非目标

- 不做用户登录/多租户
- 不做复杂的图表库集成，清晰可读优先于美观

## 功能需求

1. **日志流视图**：展示最近 `request_logs`，可按 IP/状态码筛选，用于展示"攻击正在发生"
2. **黑名单/限流状态视图**：展示 `ip_blacklist`/`ip_rate_limit` 当前生效记录，实时反映处置结果
3. **Agent 记忆时间线视图（核心）**：按 IP 展示 `agent_episodes` 的时间序列——同一 IP 的多轮判定摘要按时间排列，清晰展示"第一轮记录为可疑 → 第二轮结合历史记忆升级为高危 → 处置"这个演化过程，这是唯一一个直接把"记忆驱动决策"可视化的地方
4. 只读 Lambda API：简单的几个 GET endpoint（`/logs`、`/blacklist`、`/episodes?ip=`），直接查 CRDB，不需要复杂框架
5. 前端不需要框架复杂度，简单的静态页面 + fetch 调用即可，重点是信息呈现清晰

## 用到的 CockroachDB & AWS 工具

- **CockroachDB**：只读查询（`request_logs`/`ip_blacklist`/`ip_rate_limit`/`agent_episodes`）
- **AWS**：S3、CloudFront、Lambda（只读 API）

## 验收标准

- [ ] 三个视图都能正常加载真实数据
- [ ] 打一发攻击模拟后，日志流视图能在几秒内看到新记录
- [ ] 巡检跑完一轮后，黑名单视图能看到新增记录
- [ ] 记忆时间线视图能清楚展示同一 IP 多轮判定的演化（这是录制演示视频时的核心镜头）

## 负责人

Person B

## 预估工作量

2.5 天

## 依赖

PRD-01（表结构）、PRD-04/05（有真实数据产生）
