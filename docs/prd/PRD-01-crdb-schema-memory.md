# PRD-01：CockroachDB Schema & Agentic Memory 数据模型

> **状态：✅ 已完成** —— `services/crdb-schema`（commit `0808926`）。

## 目标

把"CockroachDB 是 agent 的持久记忆层"这个核心叙事落地成具体 schema：日志、语义记忆（向量）、情景记忆（episodes）、世界状态记忆（黑名单/限流）分层清晰，且都建好向量索引。这是整个项目里对 **Agentic Memory Design** 评分项最直接的支撑。

## 范围

- 全部核心表的 DDL：`request_logs`、`attack_signatures`、`agent_episodes`、`ip_blacklist`、`ip_rate_limit`、`accounts`、`task_queue`、`alert_log`
- `attack_signatures`、`agent_episodes` 的向量索引
- 种子数据：用官方/公开的攻击模式描述文本生成 embedding，灌入 `attack_signatures`
- 迁移脚本（可重复执行，支持 `ccloud`/`cockroach sql` 两种方式跑）

## 非目标

- 不包含 Lambda 侧如何调用（见 PRD-03/04）
- 不包含 Dashboard 查询逻辑（见 PRD-07）

## 功能需求

1. 按照 `docs/01-architecture.md` 第 3 节的 DDL 建全部表
2. `attack_signatures`、`agent_episodes` 的 `embedding` 列类型与 Titan Embeddings 输出维度一致（需在 PRD-00 阶段确认好维度）
3. 建向量索引，并跑一次真实的相似度检索验证召回质量（例如用"UnIoN sElEcT 变形注入"文本去检索，能召回 `sqli` 类别的种子特征）
4. 种子攻击特征至少覆盖：sqli（含编码混淆变形）、xss、idor、bruteforce、phishing/社工 五类，每类至少 3-5 条描述
5. 迁移脚本幂等（可重复跑不报错），方便团队协作和 demo 环境重建

## 用到的 CockroachDB & AWS 工具

- **CockroachDB**：Distributed Vector Indexing（核心）、ccloud CLI（跑迁移）
- **AWS**：Bedrock Titan Embeddings（生成种子数据向量，一次性脚本调用）

## 验收标准

- [ ] `ccloud`/`cockroach sql` 连进集群，`\d` 能看到全部 8 张表
- [ ] 向量索引建成功（`SHOW INDEXES` 能看到）
- [ ] 跑一条真实向量检索 query，返回结果按相似度合理排序
- [ ] 种子数据覆盖 5 大攻击类别，每类有描述文本 + embedding
- [ ] 迁移脚本可重复执行不报错

## 负责人

Person A

## 预估工作量

2 天

## 依赖

PRD-00（集群已就绪、embedding 维度已确认）
