# PRD-00：Infra & 账号 Bootstrap

> **状态：⬜ 未确认** —— 这类工作主要是账号配置/控制台操作，仓库里没有对应 commit，无法仅从代码判断完成情况，需要人工确认（见 [docs/03-open-issues.md](../03-open-issues.md)）。

## 目标

打通 AWS + CockroachDB Cloud 的账号、权限、IaC 骨架，确保后续所有 PRD 都有干净的地基可用，且 Bedrock Claude 模型访问这个最容易卡进度的审批项在 Day 1 就启动。

## 范围

- AWS 账号配置（IAM 用户/角色、区域选择）
- Amazon Bedrock Claude 模型访问权限申请
- CockroachDB Cloud 账号 + 集群创建（用 ccloud CLI，不用控制台点击）
- IaC 骨架搭建（SAM / CDK / Terraform 三选一，团队按熟悉度选）
- 项目基础目录结构、CI 占位（可选）

## 非目标

- 不包含具体业务表的建表（见 PRD-01）
- 不包含 Lambda 业务逻辑代码（见 PRD-02/03/04）

## 功能需求

1. AWS 账号可用，创建一个专用 IAM 角色供后续 Lambda 使用（此阶段只需角色骨架，具体权限在 PRD-09 收紧）
2. 在目标 region 申请 Bedrock Claude 模型访问权限（**Day 1 立即执行**，因为部分账号需要审批，可能有延迟）
3. 用 `ccloud` CLI（而不是 Web 控制台）创建 CockroachDB Cloud 集群，记录连接串到 Secrets Manager
4. 确认集群 CRDB 版本支持 `VECTOR` 类型和向量索引语法
5. 搭建 IaC 骨架：能一键部署/销毁基础设施（哪怕暂时是空 stack）
6. 项目仓库初始化：`git init`、目录结构、`.gitignore`

## 用到的 CockroachDB & AWS 工具

- **CockroachDB**：ccloud CLI（集群创建）
- **AWS**：IAM、Secrets Manager、（区域内）Bedrock 权限申请

## 验收标准

- [ ] `ccloud cluster list` 能看到刚创建的集群，且是通过 CLI 命令创建的（非控制台）
- [ ] 能用 `cockroach sql` 连上集群并执行 `SELECT version();`
- [ ] Bedrock 模型访问权限申请已提交（哪怕还在审批中，也要在 Day 1 提交）
- [ ] IaC 骨架能成功 `deploy` 一个空 stack 并 `destroy` 干净
- [ ] Secrets Manager 里能看到 CRDB 连接串 secret

## 负责人

A + B 共同（Day 1 优先级最高的任务，两人并行处理不同子项）

## 预估工作量

1.5 天

## 依赖

无（第一个 PRD）
