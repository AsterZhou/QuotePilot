# 批次一收尾记录 · 2026-11-08

状态：代码与测试已继续推进；现网备份、部署、公网验收和真实联合搜索仍有阻塞。未进入第二批。
本记录接续 `BATCH1_ACCEPTANCE.md`，基线远程提交 `00a79a2`。

## 实际修改

- 修复 SQLGlot 对 SQLite STRFTIME 的内部函数名转换误拦截；允许受限 GROUP_CONCAT 供应商汇总，并把可用函数列表提供给规划模型。
- SQL 参数数量/语法/字段结构错误最多修正一次；权限类拒绝不重试。保存原始拒绝原因、响应 ID 和 Token 回执。
- Genesis 连接超时 10 秒、推理读超时 90 秒，不自动切模型或无限重试。对查询规划/分析使用已真实验证支持的 Responses `reasoning.effort=low`。
- AI 分析最多 10 行样本、2 条短结论，保留完整 SQL 表格；明确样本边界。分析输出预算 4096 Token，减少推理占满输出预算的情况。
- 日期证据校验同时识别实际执行 SQL 的日期字面量和绑定参数，修复合法日期说明被误拦截的一种情况。数值或引用仍不符合证据时，保留真实表格并显示分析不可用。
- 新增管理员整库下载和离线恢复工具，校验 SQLite 完整性及 SHA256，备份包含原始文件 BLOB、已提交 WAL；恢复只写新路径，拒绝覆盖旧文件。详见 `SQLITE_BACKUP.md`。

## 实测结果

| 项目 | 实际结果 |
|---|---|
| 核心回归 | 178 通过，1 条第三方弃用警告，12 个模块 |
| 前端 | 11 条 jsdom/模拟 HTTP 断言通过；JS 语法和 git diff 检查通过 |
| 主要真实 NL 查询 | 最新保留结果合计 10/10 达到预期；来自多轮定向复测，不能描述为最终版本单轮全通过 |
| 连续追问 | 查询完成；部分完整流程的 AI 分析仍降级 |
| 供应商完整查询与分析 | 最终定向复测 completed/generated，44.44 秒；先前超时、函数误拦截及分析失败没有算作成功 |
| 独立分析复测 | 供应商、询价增长、连续追问 3/3 generated；基于先前真实 SQLite 结果重新分析，不冒充重跑完整流程 |
| 全流程 AI 稳定性 | 尚未完全解决；最新客户查询/连续追问中仍有数值证据校验拒绝 |
| 整库备份/恢复 | 本地 3 项实际文件测试通过；现网全量快照未下载 |
| 真实外部搜索 | 0/3 成功，来源链接核验 0 条 |
| 内外部联合分析 | 未通过真实端到端验收 |
| 线上部署/公网验收 | 未触发部署；本轮公网 HTTP 请求超时，未声称网站正常 |

响应 ID、Token 回执、失败任务 ID 和追踪信息见 `evidence/batch1/closeout.json`。原始合成结果仅保存在隔离工作区，不把业务库或凭据提交 Git。
验收检查比例按原定义为 10/14=71.4%（10 条内部查询 + 3 条搜索 + 1 条联合）；不包含上线准备，不能用作可上线完成度。

## Genesis / MOI 原生搜索调查

1. 复用原有 Key，Genesis `/v1/models` 200、MOI 工作区读取 200；没有要求新模型 Key。
2. 向现用 `qwen3.8-flash` Responses 请求原生 Web Search，返回 HTTP 503 / `endpoint_capability_mismatch`，该模型端点不能满足请求。
3. 普通 MOI 工具目录返回 200、0 条，随后继续读取系统 Agent，发现 6 个可见系统助手。**目录为空不等于原生搜索不存在。**
4. MOMO 系统助手声明绑定 `moi_web_search`。指定 `tool_workspace_id=system` 后，搜索工具详情读取 200，标记 active、bindable，Agent Card 也返回 200。
5. 经官方工作区级 A2A 接口执行一次只读搜索测试，请求 HTTP 200，但任务实际为 **failed**，原因为 `reason.agent_runtime.provider_unavailable`，没有返回搜索来源。

实际失败任务：`art-b10f44b7b91da6d1919012311d6a518628fbcce3d53d507b`。
追踪 ID：`trace-e1007d3ab9a0f7c3c51ee450e6da706c35c80935da4ad6b7`。
保留这些信息供平台排障，未自动发送邮件或创建支持工单。

结论：平台具有原生搜索定义，但当前真实执行失败；不能凭此宣布已完成集成，也不能断言一定需要第三方 Key。
没有创建第三方搜索账号、配置新的搜索 Key、购买计算实例或升级套餐。

可复现诊断（已有服务端凭据与 MOI_WORKSPACE_ID）：

```bash
PYTHONPATH=. python scripts/probe_moi_search.py --query 'LM358 manufacturer Texas Instruments datasheet'
```

此脚本仅做一次任务诊断；任务 completed 之后仍须核对真实工具结果及链接，不能用模型记忆里的 URL 充当搜索成功。

## 现网数据与部署阻塞

当前服务 `srv-dbni3bk9v7es73cr4rd0` 为 Render Free、Docker、autoDeploy off、分支 release-v0.7。本次没有修改这些设置。
官方 Free 文档明确没有 Shell/SSH/one-off jobs，临时磁盘会随重新部署、重启、休眠丢失。
旧线上代码无整库下载接口。现有连接也无远程执行/下载 SQLite 功能，所以无法证明旧数据已备份。
Render 浏览器已退出登录；用户选择 GitHub 登录后，网站提示该账号只连接部署、没有绑定为登录方式。未完成登录，也未修改登录凭据。
公网 `/healthz`、`/api/health`、`/api/admin/backup/download`、`/login` 本轮 HTTP 请求均 ReadTimeout，不能确认当前实例内容。

新增备份端点要部署之后才能使用，**不能反过来解决部署前旧实例的备份**。
继续部署需要：可核验的旧整库备份，或用户明确确认现网新增数据允许放弃/重置。这是实际数据丢失风险，不能根据默认演示素材推断授权。

## 剩余操作及第二批衔接

1. 取得旧备份并验证恢复，或得到现网演示数据可重置的明确确认。
2. 保持 Free，通过 GitHub 分支推进部署，记录部署 ID、最终 live 状态，完成管理员登录/权限、原有流程与查询中心公网验证。
3. 处理 MOI 原生 Agent provider_unavailable；恢复后跑 3 个真实搜索并验证来源链接，再跑联合分析。仅在另行授权新搜索 Key 后才启用第三方备用。
4. 继续收敛 AI 分析数值证据降级及请求延迟；失败记录必须保留。
5. 第一批上述验收完成后，按已授权顺序进入第二批字段级证据、复核与审计开发；当前不提前标记第二批启动。

## 修改文件

`quotepilot/providers.py`, `quotepilot/query_center.py`, `quotepilot/query_sql.py`, `quotepilot/backups.py`, `server.py`,
`tests/test_query_center.py`, `tests/test_genesis_workflow.py`, `tests/test_backups.py`,
`scripts/restore_sqlite.py`, `scripts/recheck_batch1_analysis.py`, `scripts/probe_moi_search.py`,
`docs/SQLITE_BACKUP.md`, `docs/BATCH1_CLOSEOUT.md`, `evidence/batch1/closeout.json`, `.gitignore`, `README.md`。

当前官方依据（已读取）：

- https://render.com/docs/free.md
- https://render.com/docs/deploys.md
- https://render.com/docs/health-checks.md
- https://docs.matrixorigin.cn/moi/en/5.0/reference/api/ai-studio/agents/agent-invocation/call-agent-from-agent.html
- https://docs.matrixorigin.cn/moi/en/5.0/reference/api/ai-studio/agents/tools/get-tool.html
- https://docs.matrixorigin.cn/moi/en/5.0/reference/api/genesis/text-generation/responses.html
