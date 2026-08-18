# Devpost 提交表单文案（PRD-10 交付物）

对照 `CockroachDB × AWS Hackathon - Build with Agentic Memory.md`（"What to Submit"章节）逐项
准备好的文案，提交时直接复制粘贴，避免临交前现想。英文写就是因为 Devpost 表单是英文的。

## 提交清单核对（对照 docs/01-architecture.md §6 / 原始要求）

- [ ] 公开开源仓库 URL（GitHub About 区域需能自动识别显示 LICENSE —— `LICENSE` 文件已加，MIT，
      仓库需设为 public 之后 GitHub 会自动识别）
- [ ] README 含 setup/run 说明 —— 已完成，见根目录 `README.md`
- [ ] Functional demo app 的可访问 URL —— **待补**：部署 `services/demo-target-app` 后填入
- [ ] <3 分钟视频，YouTube/Vimeo 公开，展示 CockroachDB 记忆层实际生效 —— **待录制**，剧本见
      `docs/05-demo-script.md`
- [ ] 明确写出用到的 CockroachDB 工具及具体用途 —— 见下方
- [ ] 明确写出用到的 AWS 服务及具体用途 —— 见下方
- [ ] 架构图 —— 已完成，见根目录 `README.md`（mermaid，突出 CockroachDB 作为记忆层）
- [ ] （可选）CockroachDB AI 工具使用反馈 —— 见下方

## 一句话定位（tagline）

> CR-Sentinel is a website security agent whose memory is CockroachDB — it recalls
> semantically similar past attacks and its own history with a specific IP before every
> verdict, catching obfuscated injection, slow brute force, and chained intrusions that
> signature-based WAFs structurally miss.

## Project description（表单正文，可直接粘贴，必要时精简）

CR-Sentinel is a lightweight, AI-driven security monitoring agent for web applications,
built for the CockroachDB × AWS "Build with Agentic Memory" hackathon. Traditional WAFs
and IDS rely on string matching and fixed thresholds — they recognize templates, not
intent, and miss attacks that don't match a known signature. CR-Sentinel's core idea is
that **CockroachDB is the agent's actual memory, not a log sink**: every patrol round,
before Claude judges new traffic, it first recalls (1) semantically similar attack
signatures via CockroachDB's distributed vector index, and (2) the specific IP's own
history of past verdicts. A second suspicious round from an IP already flagged escalates
instead of resetting to "normal" — because the memory persists and is actually queried,
not because of a prompt trick.

The system has two layers: an AWS Lambda-based patrol agent runs every 2-5 minutes
(EventBridge Scheduler), reads recent traffic over CockroachDB's Managed MCP Server
(read-only), recalls vector-indexed attack signatures and episodic memory, and asks
Bedrock Claude (forced tool-use) for a structured verdict. High-risk verdicts trigger
disposal writes (blacklist/rate-limit/account lock) over an independent least-privilege
write role, plus an SNS email alert. A second, millisecond-latency layer — a gateway
check on the demo target app itself — covers the gap between attacks and the next patrol
round. A Security Ops Dashboard (S3 + CloudFront + a read-only Lambda API) makes the
memory visible: a timeline of one IP's `agent_episodes` history, showing the verdict
escalate round over round.

## CockroachDB 工具及具体用途

**必须至少用 2 项，这个项目用了 2 项（第三项 ccloud CLI 是人工部署步骤，未体现为自动化代码）：**

1. **CockroachDB Cloud Managed MCP Server** (`https://cockroachlabs.cloud/mcp`) — the
   patrol agent's *entire* read path goes through this, read-only: recent `request_logs`,
   semantic recall against `attack_signatures`, and per-IP `agent_episodes` history are
   all `select_query` MCP tool calls, never a direct SQL connection from the agent's read
   side. Code: `services/patrol-agent/patrol_agent/mcp_read_client.py`.
2. **Distributed Vector Indexing** — `attack_signatures` and `agent_episodes` both carry a
   `VECTOR(1024)` column (Amazon Titan Embeddings V2) with a `CREATE VECTOR INDEX`.
   Semantic recall of known attack patterns, and of an IP's own episodic history, both run
   as `SELECT ... ORDER BY embedding <-> $vec` through that index. This is the mechanism
   that lets the agent recognize an obfuscated/encoded variant of a known attack as the
   *same* attack, not a keyword match. Code: `services/crdb-schema/migrations/001_core_tables.sql`,
   `services/patrol-agent/patrol_agent/mcp_read_client.py::semantic_search_attack_signatures`.

(Optional, not claimed as used: ccloud CLI is documented as the intended tool for cluster
provisioning/backup config in `docs/01-architecture.md` §2.1, but that's a one-time human
setup step outside this repo's automated code path, not something the agent itself calls.)

## AWS 服务及具体用途

- **Amazon Bedrock** — Claude via the Converse API with `toolChoice` forced to a single
  structured-output tool, so every verdict is `{ip, risk_level, attack_type, reasoning,
  action}`, never free text to parse; Titan Embeddings V2 for both query-time (patrol
  agent) and seed-time (attack signature library) vectors, same model for both so the
  vector space stays consistent.
- **AWS Lambda** — every service (demo target app, patrol agent, dashboard API) runs as
  Lambda functions, no persistent servers, scale-to-zero when idle.
- **Amazon API Gateway** — fronts the demo target app (the attack surface, with a
  millisecond-latency blacklist/rate-limit gate in front of every handler) and the
  dashboard's read-only API.
- **Amazon EventBridge Scheduler** — triggers the patrol agent every 2-5 minutes.
- **Amazon SNS** — emails a human on every high-risk verdict, with the IP, attack type, AI
  reasoning, and the action taken.
- **Amazon S3 + CloudFront** — static hosting for the Dashboard frontend (Origin Access
  Control, no public bucket).
- **Amazon CloudWatch** — custom per-round metrics (logs read, high/low-risk verdict
  counts, degraded-round count), alarms on function errors and sustained CockroachDB-MCP
  outages, and a dashboard.
- **AWS Secrets Manager** — every credential (CockroachDB connection strings, MCP API key)
  is injected into Lambda environment variables from Secrets Manager at deploy time;
  nothing is hardcoded in the repo (verified by a repo-wide sweep, see
  `docs/06-production-readiness.md` §2).
- **AWS IAM** — least-privilege per function; e.g. the patrol agent's Bedrock permission is
  scoped to the two specific foundation-model ARNs it calls, not `Resource: "*"`. Full
  table in `docs/06-production-readiness.md` §1.

## （可选）CockroachDB AI 工具使用反馈

> 待正式部署、实际跑过一轮真实 MCP 调用后再补充真实体验——占位，不要在没有真实使用体验的情况下
> 编造反馈。

## 架构图

见根目录 `README.md` 的 mermaid 架构图（GitHub 会原生渲染），强调"CockroachDB 作为记忆层"这个
核心叙事：agent 的每一次判断都先经过 MCP 只读通道向 CockroachDB"回忆"，而不是画成一张普通的服务
拓扑图。
