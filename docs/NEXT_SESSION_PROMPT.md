# 下一轮会话的开场提示词（2026-10-21）

把下面这段整体发给新会话即可。

---

你接手 AgentEvalLab 的开发。这是一个基于 Pi Agent 0.87.1 的单模型评测项目，目前还处在完善评测项目本身的阶段，没有进入正式的模型评测。

**开始前先读：**

- `docs/HANDOFF.md`
- `docs/plans/PLAN-006-suite-runner-and-hardening-round-2.md`（本轮计划，用户已认可）
- `docs/reviews/2026-10-20-hardening-round.md`（上一轮的结果和结论）
- 记忆目录里的 `dev-run-policy`、`project-scope-and-decisions` 和 `sandbox-dev-notes`

**本轮目标：**

1. **先做 PLAN-006 的 Part A：一键式 suite runner。** 指定模型和要跑的族之后，用一条后台命令完成全部步骤：冻结出一个 worktree、生成 plan、预检、用零 token 的 null-agent 冒烟、并发运行、对基础设施失败重试一次，最后输出一份跨族报告。同时写好离线测试，并用 deepseek-flash 加一个参考模型、两个族，端到端跑通一次。
2. **再做 Part B 的加难：** 顺序是 B1（E4 加压缩题，并正式跑 speedup 0.4.1）、B2（T1 深度阶梯）、B3（T2 0.3.0，改为政策内优化）、B4（E3 加第 6 阶段"规模"）。目标是大多数族里 deepseek-flash 的得分在 80% 左右或以下，少数略高于 80% 可以接受。

**必须遵守：**

- **模型与额度。** 开发轮次只用 deepseek-flash，外加两个左右的参考模型，从 mimo-v2.6-flash、qwen3.8-flash、glm-5.3 / glm-5.3-flash、step-5-preview 里按需选，最多三个。SuperAI 中转站（airy.work，即 glm、step、luna）最多选一个，因为那边余额很少。不用 pro 模型，每题只跑 1 次重复。目前额度情况：deepseek 和 qwen 充足，MiMo 约剩一半。每轮发起前先估算 token 用量。
- **自动化。** 先预检，再一次性在后台发起，等完成通知到了再读报告验收。不要轮询，也不要盯着运行。只跑本轮改动过的族，能合并成一轮的就合并。
- **评分原则（PLAN-005）。**
  - 每一项扣分都必须能归因到模型本身；评分器或题目有缺陷，就修复并升版本号。
  - 格式错误扣 20%，其余照常给部分分。
  - 每道题只有一个充足的预算，开场就告诉模型，并在用到 50%、75%、90% 时提醒。
  - 思考档位用中档。
  - 只有任务的总预算可以截停模型：单次回复的上限是 131,072 tokens 和 524,288 字符。
- **工程规范。**
  - 改动 `task-library/` 之后，重建对应的包，更新 plan 里的 `packageManifestSha256`，再运行 `python3 scripts/task_packages.py check`。
  - 提交时使用 `git -c user.name=liuyijie -c user.email=126372470+Ctrl1CandV@users.noreply.github.com commit`，提交信息结尾加 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。只提交，不推送，推送由用户来做。
  - 不要提交 `.env`，也不要提交沙箱生成的占位文件（`.claude/`、`.mcp.json`）。
- **沟通。** 用中文回复，说清楚做了什么、结果如何、还需要用户决定什么。
