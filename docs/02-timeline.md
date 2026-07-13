# CR-Sentinel 3 周 2 人 Timeline

## 角色分工（默认，可调整）

- **Person A（Agent Lead）**：CRDB schema/向量、MCP 接入、Bedrock 推理循环、PatrolAgentLambda、处置写入逻辑
- **Person B（Platform Lead）**：demo 靶场应用、API Gateway 拦截层、Dashboard、IaC/部署、攻击模拟脚本、视频与提交材料

两人角色围绕各自主导的 PRD 展开（见 `prd/` 目录），但集成节点（Week1 周末、Week2 周末、Week3 联调）需要两人一起 review。

## Week 1 — 地基（账号 / schema / 骨架）

对应 PRD-00、PRD-01、PRD-02（前半）、PRD-03（前半）

| Day | Person A | Person B |
|---|---|---|
| D1 | 注册/配置 AWS + CockroachDB Cloud 账号；**立刻申请 Bedrock Claude 模型访问权限**（可能有审批延迟，第一件事就做）；跑通 MCP Server 只读连接 spike | 用 ccloud CLI 创建 CRDB 集群；搭 IaC 骨架（SAM/CDK/Terraform 三选一）；起 demo 靶场 Lambda 骨架 |
| D2 | 建 `request_logs`/`attack_signatures`/`agent_episodes` 等全部表 + 向量索引；跑通向量检索 demo query | 完成靶场登录/IDOR/评论三个业务端点；接入 `request_logs` 写入 |
| D3 | 跑通 Bedrock Claude tool-use 最小 demo（单条日志 → 结构化判定输出） | API Gateway 挂到靶场；起 CloudWatch 基础日志 |
| D4 | 用官方攻击描述文本生成 embedding，灌入 `attack_signatures`（种子数据） | 靶场加"管理后台探测路径"端点；补 `accounts` 表演示数据 |
| D5 | PatrolAgentLambda 骨架：MCP 读 + 向量召回，组装 prompt（不含写入） | Secrets Manager 存 CRDB 独立写入凭证；起最小权限写入 IAM role |
| 周末缓冲 | 两人对齐集成点，跑一次端到端只读链路 review | 同左 |

**Week 1 出口标准**：账号/权限全部就绪，schema 建完且向量检索可用，靶场能产生真实日志，PatrolAgentLambda 能读到日志并让 Claude 输出一次结构化判定（还不写库）。

## Week 2 — 核心闭环（检测 → 处置 → 拦截）

对应 PRD-03（后半）、PRD-04、PRD-05、PRD-06、PRD-07（前半）、PRD-08（前半）

| Day | Person A | Person B |
|---|---|---|
| D6 | 处置动作写入逻辑：黑名单/限流/锁账号/episodes/task_queue | API Gateway 拦截逻辑：请求先查 `ip_blacklist`/`ip_rate_limit` |
| D7 | 打通"判定 → 写入 → 下一轮巡检读到记忆"闭环 | 攻击模拟脚本 v1：慢速爆破、IDOR 遍历 |
| D8 | 接入 SNS 高危告警推送 | 攻击模拟脚本 v2：编码混淆注入、社工钓鱼文本 |
| D9 | 端到端联调：跑一次完整"攻击 → 检测 → 拉黑 → 网关拒绝"链路 | Dashboard v1：日志流 + 黑名单表格 |
| D10 | 处理链式入侵场景（跨请求关联：探测 → 爆破 → 越权 → 后台扫描） | Dashboard v2：agent 推理摘要时间线（体现"记忆"） |
| 周末缓冲 | 全链路 review + bug 清单 | 同左 |

**Week 2 出口标准**：完整闭环可复现——打一发攻击，等一轮巡检，看到黑名单出现记录，再打一次同样请求被网关拒绝；Dashboard 能实时看到这个过程；同一 IP 第二次被检测时，能看到 agent 参考了上一轮的记忆。

## Week 3 — 生产就绪 + 打磨 + 提交

对应 PRD-07（收尾）、PRD-08（收尾）、PRD-09、PRD-10

| Day | Person A | Person B |
|---|---|---|
| D11 | IAM 最小权限收紧、Secrets Manager 全量替换硬编码凭证、幂等性检查 | Dashboard 打磨、加错误态/加载态 |
| D12 | CloudWatch 指标/告警看板；重试/超时/降级处理 | 攻击剧本最终定稿（8 大场景挑 3-4 个最有戏剧张力的） |
| D13 | （可选）ccloud CLI 审计日志接入展示；Agent Skills 使用说明整理 | 架构图绘制（draw.io/mermaid） |
| D14 | 全链路压测/边界 case（无攻击、重复攻击、误报场景） | 英文 README 初稿 + LICENSE(MIT) |
| D15 | 联调修 bug | 录像脚本撰写 |
| D16 | 修 bug、buffer | 正式录制 <3min 演示视频 |
| D17 | 联合 review 提交材料 | 视频剪辑、上传 YouTube/Vimeo（公开） |
| D18-19 | buffer（AWS 权限/模型访问延迟等意外情况的缓冲） | 同左 |
| D20 | 最终提交材料核对（对照 `prd/PRD-10-submission-package.md` 清单） | 同左 |
| D21 | 提交 | 提交 |

**Week 3 出口标准**：符合 Devpost 提交要求的全部材料齐备并已提交（公开仓库+License、demo URL、<3min 公开视频、CockroachDB/AWS 工具使用说明、可选架构图）。

## 关键风险与缓冲策略

- **Bedrock 模型访问审批延迟**：Day 1 第一件事就申请，不要拖到需要用的时候才申请
- **MCP Server 实际工具名与假设不符**：Day 1 spike 就要核实，避免 Week 2 才发现要返工
- **两人并行开发的集成冲突**：每周末安排一次强制 review/集成检查点，不要攒到最后
- **D18-19 是硬缓冲**：如果前面进度顺利，可以提前用来做 Agent Skills Repo 等可选加分项；如果进度滞后，这两天是唯一的容错空间
