# CR-Sentinel 详细架构与技术方案

> CockroachDB × AWS Hackathon — Build with Agentic Memory
> 产品：CR-Sentinel —— 基于 CockroachDB 长期记忆 + Bedrock Claude 语义推理的轻量级网站安全监控 agent

## 0. 一句话定位

传统 WAF/IDS 只会"字符串匹配 + 固定阈值"，只认模板不认逻辑；CR-Sentinel 让 CockroachDB 成为 agent 真正的**持久记忆**——攻击语义特征、历史决策、IP 画像全部沉淀在 CRDB 里，每一轮巡检 agent 都先"回忆"再判断，从而识别编码变形注入、0Day、慢速爆破、跨请求链式入侵、纯业务逻辑越权等传统方案的天然盲区。

## 1. 评分标准 → 功能映射

这是贯穿整个方案的核心指导原则，所有技术决策都要能回答"这个设计对应哪一项评分标准"。

| 评分项 | 对应设计 |
|---|---|
| **Agentic Memory Design** | CockroachDB 不只是日志表：`attack_signatures`（向量语义记忆）+ `agent_episodes`（每轮巡检的判断与推理过程，agent 的"情景记忆"，下一轮巡检会先读这张表再决策）+ `ip_blacklist`/`ip_rate_limit`（世界状态记忆）。Agent 每次决策前必须先"回忆"（向量检索 + 历史记录），而不是无状态单次判断 |
| **Technical Implementation** | 同时使用 MCP Server（只读）+ Distributed Vector Indexing + ccloud CLI（集群自动化）3 个 CockroachDB 工具；MCP 只读 + 独立最小权限写入通道体现"正确、安全地使用工具" |
| **Real-World Impact** | `rawmaterial.txt` 里"传统 WAF vs AI"的 8 大场景（编码混淆注入、0Day、链式入侵、慢速爆破、业务逻辑漏洞、盲注、社工钓鱼、告警风暴）直接作为 demo 攻击剧本，证明真实价值而不是玩具场景 |
| **Production Readiness** | IAM 最小权限、Secrets Manager 管理 CRDB 凭证、CloudWatch 可观测性、MCP 只读隔离写权限、幂等的自动处置动作、双层防护（网关基础拦截 + AI 深度巡检）应对"5 分钟延迟"这个已知短板 |
| **Creativity & Originality** | 卖点不是"又一个聊天机器人加了记忆"，而是"agent 的记忆本身构成安全能力"——AI 通过持续积累的攻击记忆（向量特征库 + 历史 IP 画像）识别传统正则/阈值永远抓不到的变形攻击和链式入侵 |

## 2. 系统组件

### 2.1 存储与记忆层 —— CockroachDB Cloud

承载：访问日志、攻击特征向量库、agent 决策记忆（episodes）、黑名单/限流表、任务队列、告警表、demo 账号表。

CockroachDB 工具使用（覆盖 4 项中的 3 项，满足"至少 2 项"要求并留有余量）：

- **MCP Server（只读模式）**：Patrol Agent 通过 MCP client 调用只读查询工具读最近日志、历史黑名单；调用语义检索工具做攻击特征相似度匹配。使用官方 Cloud Console 生成的配置片段接入，不搭自定义代理。
- **Distributed Vector Indexing**：`attack_signatures`、`agent_episodes` 两张表的 `embedding VECTOR(n)` 列建向量索引，用于攻击语义比对和"回忆"过去类似事件，随数据量增长依旧保持低延迟检索。
- **ccloud CLI（agent-ready）**：集群创建、备份策略配置、审计日志查看全部走 CLI（写进 setup 脚本 / Makefile），不用控制台点击，体现"agent-ready"的一致 noun-verb 操作方式。
- **Agent Skills Repo（可选/时间富余再做）**：开发阶段用官方 CockroachDB Agent Skill 辅助 schema 设计和查询优化决策，README 中注明使用方式。

### 2.2 巡检执行层 —— AWS Lambda + EventBridge Scheduler

`PatrolAgentLambda`：EventBridge 每 2–5 分钟触发一次，无常驻服务器，闲时零开销，按量计费。

内部封装：
- MCP client（只读）—— 读日志与做语义检索
- CRDB 直连写入 client（独立凭证，来自 Secrets Manager，最小权限）—— 执行处置动作

单次巡检步骤：读日志 → 向量检索历史攻击特征/记忆 → 组装 prompt 交给 Bedrock → 解析结构化判定 → 执行处置写入 → 写 episodic memory。

### 2.3 推理大脑 —— Amazon Bedrock（Claude，tool use）

只做语义判断，不直接碰网络、不直接写库，保持职责单一、易于审计。

- 输入：本轮新日志 + 向量检索召回的历史相似攻击/记忆摘要 + 静态业务规则
- 输出：结构化 JSON（IP、风险等级 normal/low/high、攻击类型、推荐处置动作、推理摘要）
- Embedding 模型：Amazon Titan Embeddings，写入 `attack_signatures`/`agent_episodes` 向量列时使用同一模型，保证向量空间一致，避免语义检索失真。

### 2.4 处置执行层 —— Lambda + CRDB 独立写入通道

CockroachDB Cloud MCP Server 官方默认是 read-only（安全优先）。CR-Sentinel 不去挑战这个默认值，而是把"读"和"写"拆成两条职责分离的通道：

- **读**：MCP Server 只读模式（日志查询 + 向量检索）
- **写**：独立的最小权限 SQL 连接，凭证存 Secrets Manager，只授予对 `ip_blacklist`/`ip_rate_limit`/`accounts`/`agent_episodes`/`task_queue`/`alert_log` 这几张表的 INSERT/UPDATE 权限，不给 DROP/ALTER/DELETE

Bedrock 返回结构化处置指令后，`PatrolAgentLambda` 通过写入通道执行：

- 高危 → `ip_blacklist` 插入（临时/永久）
- 中危扫描 → `ip_rate_limit` 插入
- 账号被盗 → `accounts` 表锁定 + 强制登出
- 通用 → `task_queue` 写入加固建议、`agent_episodes` 写入本轮记忆
- 严重告警 → `alert_log` 写入，触发 SNS 通知

这个拆分本身就是一个可以在提交材料里明确讲的 Production Readiness 亮点：职责分离、最小权限、审计友好。

### 2.5 执行拦截层 —— API Gateway（前置于 demo 靶场应用）

每次请求先查 `ip_blacklist`/`ip_rate_limit`（轻量读，CRDB 延迟可接受），命中直接拒绝。

这一层是"毫秒级基础防护"，弥补 5 分钟批量巡检的实时性短板——双层防护：网关做即时基础拦截，AI 做深度事后巡检和高级入侵识别。

### 2.6 Demo 靶场应用 —— Lambda + API Gateway

故意包含几个"业务层漏洞"端点用于攻击剧本：

- 登录接口（弱密码 / 慢速爆破场景）
- `?id=` 查询接口（IDOR 越权场景）
- 评论/留言接口（社工钓鱼文本、编码变形 XSS 场景）
- 管理后台路径（扫描探测场景）

每次请求同步写一条日志到 `request_logs`，轻量写入，不额外加中间件。

### 2.7 可观测性 / 告警 / 前端

- **CloudWatch**：Lambda 执行日志、错误率、巡检延迟指标看板
- **SNS**：高危告警推送（邮件），demo 中现场触发一条真实告警
- **S3 + CloudFront**：静态 Security Ops Dashboard 托管；同时作为原始日志冷归档，对应比赛 AWS 服务清单里的 "Amazon S3 — artifact storage"
- **Dashboard**：通过只读 Lambda API 读 CRDB，实时展示日志流、agent 本轮推理摘要、黑名单变化、历史记忆时间线——这是让评委"看得见记忆在起作用"的关键界面，直接服务于 Agentic Memory Design 评分项

## 3. CockroachDB 数据模型（Agentic Memory 的落地核心）

```sql
-- 原始访问日志（采集层）
CREATE TABLE request_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts TIMESTAMPTZ DEFAULT now(),
  src_ip STRING,
  method STRING,
  path STRING,
  query_params STRING,
  body_snippet STRING,
  user_agent STRING,
  status_code INT,
  user_id STRING,
  response_time_ms INT
);
CREATE INDEX ON request_logs (ts, src_ip);

-- 攻击特征语义库（长期语义记忆）
CREATE TABLE attack_signatures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category STRING,          -- sqli/xss/idor/bruteforce/phishing/...
  description STRING,
  severity STRING,
  embedding VECTOR(1024),   -- Titan Embeddings 维度
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE VECTOR INDEX ON attack_signatures (embedding);

-- agent 决策记忆（情景记忆，每轮巡检的"回忆"来源）
CREATE TABLE agent_episodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts TIMESTAMPTZ DEFAULT now(),
  ip STRING,
  risk_level STRING,        -- normal/low/high
  attack_type STRING,
  reasoning_summary STRING, -- Claude 输出的推理摘要
  action_taken STRING,
  embedding VECTOR(1024),
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE VECTOR INDEX ON agent_episodes (embedding);
CREATE INDEX ON agent_episodes (ip, ts);

-- 封禁名单（世界状态记忆，网关强依赖读）
CREATE TABLE ip_blacklist (
  ip STRING PRIMARY KEY,
  risk_level STRING,
  block_until TIMESTAMPTZ,
  attack_reason STRING,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 限流规则
CREATE TABLE ip_rate_limit (
  ip STRING PRIMARY KEY,
  limit_per_min INT,
  expires_at TIMESTAMPTZ
);

-- demo 账号表（用于演示账号锁定处置）
CREATE TABLE accounts (
  user_id STRING PRIMARY KEY,
  username STRING,
  locked BOOL DEFAULT false,
  locked_reason STRING,
  force_logout_at TIMESTAMPTZ
);

-- 加固任务队列（异步）
CREATE TABLE task_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type STRING,
  payload JSONB,
  status STRING DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 告警表
CREATE TABLE alert_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts TIMESTAMPTZ DEFAULT now(),
  severity STRING,
  message STRING,
  sent BOOL DEFAULT false
);
```

## 4. 巡检循环（agent 主流程）

```
EventBridge 触发 PatrolAgentLambda
  → MCP(只读) run_read_query: 近 N 分钟 request_logs
  → MCP(只读) vector_search: 对可疑请求做 attack_signatures 语义召回
  → 直连读: 近期同 IP 的 agent_episodes 历史记忆（是否已处置过/是否是常客）
  → 组装 prompt(日志 + 召回的攻击特征 + 该IP历史记忆) → Bedrock Claude (tool use)
  → 解析结构化输出 {ip, risk_level, attack_type, action, reasoning}
  → 按 risk_level 分支：
      normal      → 不写入，结束
      low         → 写 agent_episodes（记录，不处置）
      high        → 写 ip_blacklist / ip_rate_limit / 锁账号 + 写 agent_episodes + 写 alert_log
  → SNS 推送高危告警
```

真实攻击闭环示例（延时盲注）：

1. 攻击者连续发送 `?id=1' sleep(2)--` 多条请求，日志落 `request_logs`
2. 定时 Lambda 启动，MCP 读取这批日志交给 Claude
3. Claude 识别：该 IP 持续使用延时注入，属于高危拖库攻击，输出处置指令：封禁 IP 24 小时
4. Lambda 通过写入通道执行 SQL，将 IP 插入 `ip_blacklist`
5. 攻击者再次发送请求，API Gateway 查询黑名单直接拒绝
6. 本轮攻击彻底阻断，全程无人工介入

## 5. 短板与折中（诚实写进提交材料，体现 Production Readiness 思考深度）

| 短板 | 折中方案 |
|---|---|
| 5 分钟批量巡检，无法做到毫秒级实时拦截 | API Gateway 做基础即时拦截（黑名单查询），AI 做深度事后巡检、高级入侵识别，双层防护 |
| 高并发超大流量场景成本上升 | 只采集异常响应码、高频 IP 日志，过滤正常静态资源请求，减少数据量 |
| 仅覆盖应用层安全，不监控底层服务器漏洞 | 明确定位：专注网站业务层入侵与请求攻击监控，不替代主机安全工具 |

## 6. 风险与验证清单（Week 1 Day 1 必须先跑通的 spike）

1. 确认 CockroachDB Cloud MCP Server 实际暴露的工具名/参数（`run_read_query`、`vector_search` 是基于产品描述的假设名，需要对照 Cloud Console 生成的 MCP 配置片段核实）
2. 立刻申请 Amazon Bedrock Claude 模型访问权限（部分区域/模型要账号级审批，可能有延迟，Day 1 第一件事就做，不要等到 Week 2）
3. 确认目标 CRDB 版本的 `VECTOR` 类型语法、距离函数（cosine/L2）、向量索引建法
4. 确认 Titan Embeddings 输出维度与 CRDB 向量列定义一致

## 7. 技术栈总览

| 层 | 技术 |
|---|---|
| 记忆/存储 | CockroachDB Cloud（MCP Server、Distributed Vector Indexing、ccloud CLI） |
| 巡检执行 | AWS Lambda + EventBridge Scheduler |
| 推理 | Amazon Bedrock（Claude，tool use）+ Titan Embeddings |
| 拦截 | API Gateway |
| 靶场应用 | AWS Lambda + API Gateway |
| 告警 | Amazon SNS |
| 前端 | S3 + CloudFront 静态 Dashboard + 只读 Lambda API |
| 安全 | Secrets Manager、IAM 最小权限 |
| 可观测性 | CloudWatch |
