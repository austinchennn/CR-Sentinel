# TODO / 剩余工作清单

汇总现状：PRD-01 到 PRD-10 的代码/文档层面工作均已完成（见各 `docs/prd/PRD-*.md` 的状态行）。
剩下的全部是需要真实 AWS/CockroachDB Cloud 账号访问、真实部署、或真人录屏才能完成的部分——不是
代码问题，是操作问题。

## 需要人工操作（非代码，无法从这里完成）

- [ ] **PRD-00**：AWS/CockroachDB Cloud 账号、IAM、IaC 骨架、Bedrock 模型访问审批是否已就绪？
      仓库里没有对应 commit，无法从代码判断（见 `docs/03-open-issues.md` #2）。
- [ ] **PRD-06 收尾**：SNS Topic 的邮箱订阅确认（部署后点击 SNS 发来的确认邮件）——代码已完成，
      这是唯一剩的人工步骤（见 `services/patrol-agent/README.md` "Manual verification against a
      live cluster + SNS"）。
- [ ] **`BEDROCK_MODEL_ID` 确认**：`patrol_agent/config.py` 的 `BedrockConfig.model_id` 默认值
      `anthropic.claude-3-5-sonnet-20241022-v2:0` 是占位符，部署前需确认 PRD-00 实际审批通过的
      模型 ID 是否一致，不一致要通过环境变量覆盖（见 `docs/03-open-issues.md` #1）。
- [ ] PRD-09 可选项：ccloud CLI 审计日志展示——需要真实集群访问。
- [ ] PRD-10：演示视频录制 + 上传 YouTube/Vimeo（公开）；demo app 实际部署后的可访问 URL——两者
      都需要真实部署环境，见 `docs/07-devpost-submission.md` 顶部清单。

## 代码层面待决问题 —— 全部已解决

- [x] 高危判定时 episode embedding 失败会连带跳过处置动作和告警 —— 已解耦，见
      `docs/03-open-issues.md` "已修复的 bug"。
- [x] `accounts.username` 没有唯一约束 —— 已加 `migrations/002_accounts_username_unique.sql`。
- [x] `patrol_agent/embeddings.py` 与 `crdb_schema/titan_embeddings.py` 手动重复、无一致性防护
      —— 已加测试守卫。
- [x] `typing.Protocol` 接口接入类型检查 —— 每个服务加了 `mypy.ini`，
      `.github/workflows/ci.yml` 在每次 push/PR 跑 pytest + mypy，5 个服务全绿。跑 mypy 时
      顺带抓到 4 个真实的潜在 bug（模块级缓存变量标了非 `Optional` 类型但赋值 `None`），已修。
- [x] `agent_episodes`/`task_queue`/`alert_log` 在 Lambda 重试场景下可能重复写入（PRD-09 验收
      标准 5）—— 已用 `_compute_round_idempotency_key` + `migrations/003_disposal_write_idempotency.sql`
      解决，见 `docs/06-production-readiness.md` §4。
- [x] PRD-04 的"链式入侵关联分析"加强项（Week 2 D10）—— 已实现：`heuristics.py` 新增
      "一个 IP 在一轮内触碰 3 个以上敏感端点"的检测信号，prompt 里显式给出端点访问序列，
      `attack_type` 词表加入 `chained_intrusion`。

## PRD 完成情况

全部 10 个 PRD 的代码/文档层面工作已完成，见各自 `docs/prd/PRD-*.md` 状态行。PRD-00/06/09/10
剩下的都是上面"需要人工操作"清单里列出的、无法从代码仓库里完成的步骤。
