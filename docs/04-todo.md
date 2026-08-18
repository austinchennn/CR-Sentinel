# TODO / 剩余工作清单

汇总现状（截至 `main` 合并 PR #12 后）：PRD-01 到 PRD-06 均已完成并合并；PRD-00 需人工确认；
PRD-07/08/10 未开始；PRD-09 部分完成。另外 `docs/03-open-issues.md` 记录的几个待决问题
仍未处理。这份文档把两边汇总成一份可执行清单，方便直接转成 issue。

## 需要人工确认（非代码）

- [ ] **PRD-00**：AWS/CockroachDB Cloud 账号、IAM、IaC 骨架、Bedrock 模型访问审批是否已就绪？
      仓库里没有对应 commit，无法从代码判断（见 `docs/03-open-issues.md` #4）。
- [ ] **PRD-06 收尾**：SNS Topic 的邮箱订阅确认（部署后点击 SNS 发来的确认邮件）——代码已完成，
      这是唯一剩的人工步骤（见 `services/patrol-agent/README.md` "Manual verification against a
      live cluster + SNS"）。
- [ ] **`BEDROCK_MODEL_ID` 确认**：`patrol_agent/config.py` 的 `BedrockConfig.model_id` 默认值
      `anthropic.claude-3-5-sonnet-20241022-v2:0` 是占位符，部署前需确认 PRD-00 实际审批通过的
      模型 ID 是否一致，不一致要通过环境变量覆盖（见 `docs/03-open-issues.md` #2）。

## 代码层面待决问题

- [x] **高危判定时 episode embedding 失败会连带跳过处置动作和告警** —— 已解耦，见
      `docs/03-open-issues.md` "已修复的 bug" #2。
- [x] **`accounts.username` 没有唯一约束** —— 已加 `migrations/002_accounts_username_unique.sql`，
      见 `docs/03-open-issues.md` "已修复的 bug" #3。
- [x] **`patrol_agent/embeddings.py` 与 `crdb_schema/titan_embeddings.py` 手动重复、无一致性防护**
      —— 已加测试守卫，见 `docs/03-open-issues.md` "已修复的 bug" #4。
- [ ] **`typing.Protocol` 接口尚未接入类型检查**
      PR #12 给三个服务加了 `interfaces.py`，但仓库没有 `mypy` 配置/CI 步骤，目前这些 Protocol
      只在 IDE 里生效，不是强制契约。是否要加 `mypy.ini` + CI gate？

## 未开始 / 部分完成的 PRD

- [ ] **PRD-07：Security Ops Dashboard**（未开始，预估 2.5 天）——静态前端 + 只读 Lambda API +
      三个核心视图（日志流、黑名单/限流状态、agent 记忆时间线）。评委看"记忆驱动决策"最直接的
      举证点。
- [ ] **PRD-08：攻击模拟器 & 演示剧本**（未开始）——慢速爆破、IDOR 遍历、编码混淆注入等攻击脚本，
      PRD-05/07 的验收标准和演示都依赖它先跑起来。
- [ ] **PRD-09：可观测性 & 生产就绪加固**（部分完成）——重试/降级逻辑已在 PRD-03/04 实现；剩
      IAM 最小权限收紧、CloudWatch 指标看板、ccloud 审计日志展示未开始。
- [ ] **PRD-10：提交打包**（未开始）——英文 README、LICENSE、演示视频、架构图等 Devpost 提交材料。

## 建议顺序

PRD-08（攻击模拟器）先于 PRD-07（Dashboard）会更顺——Dashboard 的验收标准本身就要求"打一发攻击
模拟后能在视图里看到"，没有模拟器 Dashboard 没法端到端验证。PRD-09/PRD-10 适合放最后，因为都是
收尾/打磨性质，且不阻塞其他 PRD。
