# 演示剧本 / Demo Script（PRD-08 交付物）

供 PRD-10 录制 <3 分钟演示视频时直接使用。每个场景对应
`services/attack-simulator/attack_simulator/scenarios/` 里的一个脚本，运行命令见
`services/attack-simulator/README.md`。

## 场景 1：编码混淆变形注入（`obfuscated_sqli`）

**讲什么故事**：同一个 SQL 注入意图，用大小写穿插、URL 编码、`/**/` 拆分等 4 种不同写法发送到
`GET /profile?id=`。传统 WAF 需要为每种变形单独写规则；CR-Sentinel 的 patrol agent 通过语义
embedding 对 `attack_signatures` 做向量召回，应该把这 4 种变形都识别成同一类攻击。

**运行**：`python -m attack_simulator.cli obfuscated_sqli --base-url <demo-app-url>`

**预期看到什么结果**：等下一轮巡检后，`agent_episodes` 里该 IP 出现 `attack_type=sqli`、
`risk_level=high` 的记录；Dashboard（PRD-07）记忆时间线视图能看到这条判定，`reasoning` 字段应
体现"识别出多种变形写法背后的同一攻击意图"。

## 场景 2：慢速爆破 / 温水煮青蛙（`slow_bruteforce`）

**讲什么故事**：对同一账号尝试 6 个不同密码，请求间隔拉开，不会触发固定阈值的限流规则。
patrol agent 需要结合 `agent_episodes` 里跨多轮的历史记录，才能判断这是一次持续的爆破尝试。

**运行**：`python -m attack_simulator.cli slow_bruteforce --base-url <demo-app-url>`

**预期看到什么结果**：单独一轮巡检可能只判定为 `low`（可疑但不确定）；连续两轮之后
（同一 IP 再次出现失败登录），第二轮判定应该结合第一轮的 `agent_episodes` 记忆升级为 `high`，
`reasoning` 里应引用"上一轮已经记录过这个 IP 的可疑登录尝试"。这是演示"记忆驱动决策升级"最直
接的镜头之一。

## 场景 3：IDOR 越权遍历（`idor_enumeration`）

**讲什么故事**：请求本身完全合法（没有注入字符、没有畸形输入），只是依次遍历
`?id=u-1000,u-1001,...`。任何基于特征/正则的 WAF 对单条请求都挑不出毛病——攻击只存在于"访问
模式"里：一个 IP 连续读取多个不同用户的数据。

**运行**：`python -m attack_simulator.cli idor_enumeration --base-url <demo-app-url>`

**预期看到什么结果**：`agent_episodes` 出现 `attack_type=idor`、`risk_level=high` 的记录；
Dashboard 黑名单视图应该看到该 IP 被拉黑；`reasoning` 应体现"识别出的是访问模式异常，而非任何
单条请求的内容异常"。

## 场景 4：跨请求链式入侵（`chained_intrusion`）

**讲什么故事**：单个 IP 依次完成"探测 `/admin` → 弱密码登录成功 → 越权读取他人资料 →
再次探测 `/admin`"完整链路。任何一步单独看都只是"有点奇怪"的正常流量；串联起来才是一次完整
入侵。这是唯一直接体现"agent 参考自己过去几轮判定做出升级决策"的场景，也是 PRD-04 D10 加强项
（链式入侵关联分析）对应的演示素材。

**运行**：`python -m attack_simulator.cli chained_intrusion --base-url <demo-app-url>`

**预期看到什么结果**：Dashboard 记忆时间线视图上，该 IP 应该出现从"低危/可疑"到"高危"的清晰
演化过程，可以配合场景 2 的多轮升级一起讲。

## 建议的 3 分钟视频结构（对应 PRD-10）

1. **0:00–0:15** 一句话讲清楚 CR-Sentinel 是什么、解决什么问题（AI 驱动的自动防御 + 可读写记忆
   的 CockroachDB，而不是静态规则 WAF）。
2. **0:15–1:45** 现场跑 1-2 个场景（推荐 **场景 1**：视觉效果最直接，"4 种变形 → 1 次判定"一句
   话讲得清；或 **场景 4**：故事性最强），展示"攻击 → AI 判定 → 自动拉黑 → 网关拒绝"完整闭环。
3. **1:45–2:30** 切到 Dashboard 记忆时间线视图，讲清楚"CockroachDB 不是日志盘，是 agent 会读
   会用的记忆"——同一 IP 第二轮判定明确引用了第一轮的记录。
4. **2:30–3:00** 简要提及生产就绪设计（最小权限、双层防护：网关即时拦截 + AI 深度巡检），收尾。

## 已知限制

`slow_bruteforce`/`chained_intrusion` 的"跨轮次升级"效果依赖真实巡检间隔（`PATROL_WINDOW_MINUTES`）
和真实部署环境；本地/无部署环境下只能验证请求确实发出、`request_logs` 落库正确，无法验证
Bedrock 判定升级本身——这部分需要对照真实部署跑一次（见
`services/patrol-agent/README.md` "Manual verification against a live cluster + Bedrock"）。
