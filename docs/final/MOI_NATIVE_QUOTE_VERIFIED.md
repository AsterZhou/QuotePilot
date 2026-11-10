# QuotePilot 原生工作流报价验收

2026-11-10，上海时间。QuotePilot 验收环境从来件页启动 MOI 原工作流 v3，四个节点全部完成。合成报价 `CQ-A5C5C0B2D211457E` 已获双角色审批，成本 35.00 元，最终报价 43.74 元，PDF 与 Excel 读回一致。平台工作区为 `ec94c942-2d64-c6be-c968-e793caaef007`。应用运行于隔离 HTTPS 环境，使用独立 SQLite 与测试账号。正式 Render 服务未参与本次验收。

| 原生执行 | 工作流 ID | 执行 ID | 终态与证据 |
|---|---|---|---|
| 最小信息提取 | `a1f75c37-eb9d-57ce-bfe3-6debdf2142c3` | `9ea0945a-ec8b-4131-a000-35df3d3adbd0` | completed，提取节点 4 秒，[输入、输出和状态](../../evidence/native-quote-20261110/minimum.json) |
| SQL 独立验证 | `7e9e856c-2f0f-5241-b69a-555cdc3586b1` | `c5d7856c-90d5-43aa-8417-456e1ee8cd01` | completed，插入一行，原生与独立查询比对成功，[SQL 回执](../../evidence/native-quote-20261110/sql.json) |
| QuotePilot 原工作流 | `45e246b6-9a6f-5331-82cd-44c00f67cb18` | `84f79f23-01ac-4d3f-a5e8-4ef600f677c8` | completed，四个节点完成，[节点输入输出、时间、trace 与终态](../../evidence/native-quote-20261110/business-run.json) |

## 从 disabled 到真实执行

1. 同一测试定义只填写 `run_ref` 时，部署请求返回 HTTP 200、版本 0，底层定义 ID 和版本 ID 均为空。对同一工作流补齐绑定到 `vars.run_ref` 的必填字段 `vars_run_ref` 后，部署生成版本 1 和两个 ID。原四节点工作流修复前也只保存了 `run_ref` 默认值。历史启动时平台只返回通用 HTTP 400，未提供内部校验分支。此次对照复现了阻止部署的配置条件。[绑定对照](../../evidence/native-quote-20261110/binding-control.json)
2. 向官方 `POST /v5/workflow/v2/workflow-deployments` 提交原工作流 ID、DSL、运行表单和两个相同的默认值，得到 ready。占位引用 `QP-RESERVED-UNSTAGED` 不对应业务行。产品每次启动均将本次暂存的唯一引用写入两个字段。首次启用无需调用 resume。[实际部署请求、版本回执与最终状态](../../evidence/native-quote-20261110/deployment.json)
3. 第一次真实执行中，存入的引用和 SQL 解码出的引用相差一个尾随零字节。查询返回零行，模型收到 null，因输入校验失败而退出。修复为比较两侧的 Base64 表示，直接读取已存 Base64，再用工作流表达式解码原文。第二次执行正确取回原文，但固定模型 qwen3.8-flash 返回 “No available LLM backend or endpoint”。第三版使用工作区模型槽位，解析到 kimi-k3 并成功。实际成功未要求新建专属计算实例。[失败节点及逐字节比对](../../evidence/native-quote-20261110/diagnosis.json)
4. v3 的底层定义 ID 为 `5fd91498-94bb-4431-a170-4706e5653a09`，版本 ID 为 `86cb0c56-bd12-40b4-888b-a9ac35f3eb12`。工作流最终为 ready、活动执行为 0。独立 SQL 验证流程已暂停，新建计算实例数为 0。[资源与清理回执](../../evidence/native-quote-20261110/resources.json)

## 同一笔报价如何复验

1. 在隔离服务端配置 `QUOTEPILOT_NATIVE_RFQ=1`、`MOI_WORKSPACE_ID`、`MOI_WORKFLOW_ID`，通过密钥配置提供 `MOI_API_KEY`。若需重建部署，可参考上方部署回执内的 `request_body`，用目标验收工作流 ID 和仓库当前 `integration/rfq_native.yaml` 替换对应两项。服务端检查 ready、部署定义匹配及 run 操作后才提交。
2. 用专用管理员账号上传带新 Message-ID 的合成询价邮件，在「询价来件」内启动「MOI 原生作业」。本次原句为 “Please quote 3 EA of PN-0001, condition FN, synthetic valve spec A.” 本次应用引用为 `QN-91b5abc03a1642429b776e3d7bce3d0c`。[产品作业页实拍](../../evidence/native-quote-20261110/native-job.webp)
3. 刷新同一作业。load_rfq 读取原文，extract_rfq 返回 PN-0001、3 EA、FN 和原文字段证据。persist_suggestions 更新一行，read_back 读回该行。应用再单独查询 MatrixOne，得到查询 ID `01a1c46c-b590-7bf0-ab50-094681cc4c8e`。模型输出的 SHA-256 为 `432cf09c4197174d67fe9037774a7b175dcb166bbf982bbe7dbe6af35aedf6a7`。输入字节、实际模型输入、输出和两次读回核对成功后，应用生成待复核建议 `EX-96A91A2CB901`。[复核界面实拍](../../evidence/native-quote-20261110/native-review.webp)
4. 核对原文并采用建议，导入并确认两家合成供应商的原始报价。产品选出 SYN-Cheap，每件进价 10 元，三件的处理成本共 3 元、其他成本 2 元，合计 35 元。目标毛利率 20%，按件舍入至 14.58 元，三件总价 43.74 元。验收自动化分别使用 reviewer 与 admin 两个测试账号完成复核和审批。前端来件、原生启动和采纳通过 Chromium 操作，后续核价、审批和导出通过同一应用的业务 API 完成。[商业操作及已审批快照读回](../../evidence/native-quote-20261110/commercial.json)
5. 导出并重新解析两个文件核对金额。应用另将获批版本 v3 写入 MatrixOne 并逐字节读回，快照 SHA-256 为 `61a68e69169c064e4e58741748c9676607dee44a397a1214432516fede01bbbc`。供应商比价、核价、审批、导出和获批快照同步由 QuotePilot 执行。[PDF](../../evidence/native-quote-20261110/approved.pdf) · [Excel](../../evidence/native-quote-20261110/approved.xlsx)

## 模型调用、费用与回归

两次成功的原生推理均在 Genesis 请求日志中各匹配到唯一一条成功记录。最小节点用量为 436 输入与 92 输出，业务节点为 179 输入与 215 输出，共计 922 Token。两条记录的模型、运行时间窗口、输入和输出 Token 数与原生节点相符，结算通道为 ai_service。平台没有在两套回执中返回可作直接外键的同一个请求 ID。[Genesis 脱敏日志与账单查询响应](../../evidence/native-quote-20261110/billing.json)

两次推理的定价快照均给出 120 Credit 的单位价格。请求日志中的计费上报状态为 skipped。账户及 AI 服务账本接口对当前凭据均返回 HTTP 401，实际入账 Credit 和账户余额无法由这份回执确认，SQL 费用也没有可核实的入账条目。此次没有现金操作。[AI 服务账本 API](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/genesis/billing/usage/ai-service.html) · [Genesis 用量与计费](https://docs.matrixorigin.cn/moi/zh/5.0/guides/billing/genesis-usage.html)

代码改动集中于 `integration/rfq_native.yaml`（原生 SQL、解码与模型槽位）、`quotepilot/native_jobs.py`（输入及模型实收原文校验）和 `tests/test_native_rfq_jobs.py`（实际回执形态与尾随零字节回归）。全量自动化 280 项通过，2 条依赖弃用警告。真实失败路径记录见上述 v1、v2 回执。重复提交、异常模型结果、数据库失败恢复和并发提交的故障测试采用离线协议夹具。[回归输出](../../evidence/native-quote-20261110/test-suite.log)
