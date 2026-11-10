# QuotePilot · MOI 原生询价验收记录

**最新验收（2026-11-10 15:52，上海时间）**　原工作流 v3 已从 QuotePilot 来件页完成四节点执行，同一笔报价已双角色审批、导出并读回 MatrixOne。业务执行 ID 为 `84f79f23-01ac-4d3f-a5e8-4ef600f677c8`。[查看真实执行、复核与报价凭证](MOI_NATIVE_QUOTE_VERIFIED.md)。

## 较早的诊断记录

2026-11-10 上海时间。开发基线为独立分支 `commercial-upgrades` 的 `0c45316df283243c655bcd7c50c70c815ae9c2df`。本次在该分支提交，未部署到线上报价室。

**14:13 最新复查（上海时间）：项目令牌有效，五次只读请求均返回 HTTP 200。** 工作流仍为 disabled，触发器关闭，执行数为 0，当前身份可见的计算实例为 0。工作区返回 15 种计算规格，仅三种 task 规格启用，标价为 6、12 和 24 Credit/小时；三种 query 规格均未启用。未见已启用的零价规格。该身份的规格管理权限为 false。已暂停实例创建与运行，需赛事管理员确认并绑定可用的免费执行资源、启用此工作流。没有创建资源或生成执行 ID。[带凭据的脱敏查询记录](../../evidence/native-rfq-20261110/authenticated-preflight.json)。

13:47 的未认证探测记录在下表，14:13 的带凭据结果取代此前对当前身份和资源的判断。
## 平台返回与根因边界

| 类别 | 证据与判断 |
|---|---|
| 请求地址与身份上下文 | `POST https://api.moi.matrixorigin.cn/v5/workflow/v2/workflow-apps/{workflow_id}/executions`，使用 `X-Workspace-ID` 与服务器侧 `X-API-Key`。官方启动接口没有额外的 project_id 参数。以往同一工作区对该 workflow_id 的 GET 返回 200。 |
| 已保存的定义 | 工作区 `ec94c942-2d64-c6be-c968-e793caaef007`，工作流 `45e246b6-9a6f-5331-82cd-44c00f67cb18`。11/05 创建返回 200，一次运行模式为 one_shot，但状态 disabled，deployment.version=0，两项底层定义/版本 ID 为空。11/08 带凭据读取仍为 disabled，操作列表含 enable，没有 run。 |
| 启动错误 | 11/08 请求体为 `{"values":{"vars_run_ref":"SPRINT-SYNTHETIC-20261108"},"trigger_now":true}`。响应 HTTP 400，原始业务体为 `{"code":"ErrParamInvalid","msg":"Bad Request"}`，request/trace ID 为 `00c50a03-7d17-4bed-9e95-024d7a4e3bb4`。未收到执行 ID。11/05 单独查询过执行列表，为空。不能把 11/05 的列表当作 11/08 错误后的再次查询。 |
| 代码与参数 | 旧诊断脚本绕过 ready 检查。已保存表单同时有必填的 run_ref、绑定 vars.run_ref 的 vars_run_ref，并保存了旧 run_ref 默认值。历史启动只覆盖了后者。官方规定显式值会与默认值合并，因此原请求可能含两个不同引用。现按实际绑定发同一引用；无法回推平台当时是否在这里返回了 400。 |
| 恢复接口 | 11/05 的 `POST .../resume` 对 disabled 定义也返回了 400。官方恢复操作适用于 paused，不能据此证明已发布、启用或新建作业。 |
| 账号与资源 | 11/08 能读取模型清单、定义、规格；可见计算实例为 []，规格管理权限为 false。这不能裁定实际运行权限、可用免费额度或权限继承。SQL 与非 SQL 负载需要核对各自资源类型和绑定；未创建实例。 |
| 定义和节点 | 仓库 DSL 的四个节点依次为 load_rfq、extract_rfq、persist_suggestions 和 read_back。对照历史工作区 WorkItem schema，SQL v1 接收 sql、可返回 rows/affected_rows，LLM v3 接受 model/prompt/text、可返回 text/model/usage。节点 ID、版本和字段能对上。仅有保存回执，DSL 表达式求值、实际模型通道、输入输出形态和 SQL 执行效果仍待真机。 |
| 本轮服务返回 | 2026-11-10 13:47 上海时间，使用真实工作区请求头、无凭据 GET 指定工作流，HTTP 401 / Unauthorized，request ID 为 `0b614483-a34b-4c76-814f-7e44f2f00d53`。本开发进程未收到 MOI/Genesis 凭据。401 不能证明账户被禁用或缺少运行权限。 |

可确定的阻塞是最后一次带凭据检查时工作流未就绪。服务端未说明历史 400 的具体校验分支，应使用历史 trace ID 向管理员定位。已验证的独立模型调用、应用层 SQL 写入与读回各自有独立回执。

证据：[原始创建和详情](../../evidence/v07/native_attempt.json) · [恢复与执行列表](../../evidence/v07/native_resume.json) · [11/08 工作区及计算实例](../../evidence/sprint-p0/preflight.json) · [11/08 启动请求与响应](../../evidence/sprint-p0/live.json) · [本轮只读探测](../../evidence/native-rfq-20261110/preflight.json) · [WorkItem schema](../../evidence/v07/workitem_details.json)。

## 实现与验收结果

| 项目 | 本轮结果 |
|---|---|
| 工作流部署、发布与启用 | 沿用已有 RFQ DSL 与历史平台定义。没有新的部署回执或 ready 证据。 |
| 真实启动、执行 ID、节点结果与截图 | 本轮没有发送启动请求。无执行 ID、运行截图或成功节点记录。 |
| Genesis 原生节点与 MatrixOne 原生节点 | 尚未真实执行。原生执行、数据库读回与业务导出尚无来自同一次真实运行的证据。 |
| 工作台入口 | 独立环境启用后，管理员从已导入的询价打开「MOI 原生作业」。界面提供启动、同一询价的历史记录、刷新及按执行 ID 核对。浏览器只接触 QuotePilot API。已验证应用 HTTP 路由与 JS 语法，没有本轮浏览器端真实 MOI 验收。 |
| 业务分工 | 原生定义负责读取 RFQ 文本、模型提取、写入待复核结果、节点读回。RFQ 附件的文字解析在 QuotePilot 进行；独立供应商原件提取、比价、异常识别、Decimal 核价、版本差异、双角色审批及导出沿用 QuotePilot。供应商处理目前没有接入原生调度。 |
| 读回与人工复核 | 成功路径核对工作流与执行 ID、作业终态、四节点状态、原始输入字节、唯一行写入、原生模型输出、SQL 节点与独立 SQL 查询。复用原有数据模型验证每行来源证据，保存待复核建议。保存提取建议与本地作业完成标记位于同一事务。 |
| 失败与重试 | 上传内容、邮件、工作区和工作流共同标识一笔作业。输入写入失败可沿同一引用再试；POST 超时或返回错误则进入待核对，禁止自动重发。关联已有执行须读取平台详情并核对展开变量。作业失败、证据不符或数据库未读回时，不产生可采纳行。结果读回失败可刷新原执行。 |
| 自动化 | 全量 279 项通过，含新增 8 项；两条第三方弃用警告。新用例采用离线平台响应，覆盖并发、重复提交、远端状态未知、写入失败、结果读回恢复、异常输出、角色限制及审核后导出。合成报价 PDF 和 Excel 实际读回金额均为 43.74 CNY。 |
| 运行范围 | 本轮业务测试数据库均在临时目录；未操作线上服务、业务表或既有 SQLite。未创建计算实例或付费资源。 |

## 再次执行真实验收

1. 在隔离环境检出本次提交并安装 `requirements-tested.txt`。为验收服务指定新的 SQLite 路径、独立管理员/复核员密码及现有 HTTPS 配置。沿用原件留存和角色隔离。只放本次合成文件。
2. 配置独立服务端 `MOI_WORKSPACE_ID`、`MOI_WORKFLOW_ID` 和现有授权凭据 `MOI_API_KEY`。只读检查可使用下面的隐藏输入方式。记录当前工作流版本、触发器、运行字段、可见计算实例和是否已有可用的免费绑定。

   ```bash
   python scripts/native_rfq_preflight.py --workspace ec94c942-2d64-c6be-c968-e793caaef007 --workflow 45e246b6-9a6f-5331-82cd-44c00f67cb18 --prompt
   ```

3. 若工作流仍 disabled，向工作区管理员提供上述 ID 与历史请求追踪号，核查运行权限、已发布版本、SQL/通用资源及模型通道，绑定现有免费资源。需要付费时停止。平台可读取状态为 ready、实际 DSL 与仓库版本一致且运行表单有效后，在隔离后端设置 `QUOTEPILOT_NATIVE_RFQ=1`。本集成使用已存在的 `quotepilot.rfq_workflow_runs_v1` 合成验收表，只插入新生成的 QN 引用并核对 SHA256，不覆盖旧输入。
4. 上传一封新的合成 EML，正文写明“Please quote 3 EA of PN-0001, condition FN, synthetic valve spec A.” 在来件页打开「MOI 原生作业」，确认合成输入并启动一次。保存本地引用、平台执行 ID、四个完整节点路径及状态。若提交结果未知，在 AI Studio 查询已有记录再关联。不要为取得回执另起一单。
5. 刷新同一作业直至终态。保存 MOI 作业详情、作业结果、四个节点输入输出和平台记录；脱敏后保存 SQL 查询 ID、输入及输出 SHA256。若模型通道不能由节点输出确认，再向管理员核对调用日志与模型通道。区分执行 ID 与模型响应 ID。
6. 从已核验的作业打开待复核建议。逐行对照数量、件号、单位和证据，走原有人工确认。再上传独立合成供应商报价、确认原件并生成报价草案。测试价每件 10 元，数量 3，加工费每件 1 元，其他成本整单 2 元，运费及税为 0，目标毛利率 20%。成本 35.00 元，按单价分位舍入后总报价应为 43.74 元。
7. 业务复核员审核，另一管理员审批。分别读取导出的 PDF 文本与 Excel 单元格，对照同一报价 ID、版本和金额。将指向 MOI 执行 ID 的提取回执、人工审批记录、文件及哈希保存在同一份真实验收记录中。
8. 重复提交同一来源、模拟平台错误与无效证据、测试临时数据库写入/读回失败后恢复。在隔离测试环境使用故障注入，避免为测试失败而破坏平台资源。真实成功报告必须能沿同一笔询价追溯到所有回执。

## 修改文件

| 文件 | 作用 |
|---|---|
| `quotepilot/native_workflow.py` | 核对真实部署 DSL、表单和状态，封装启动、作业详情、节点与结果，校验回执归属。 |
| `quotepilot/native_jobs.py` | 原件暂存与读回、幂等提交、状态追踪、四节点核验、数据库一致性及人工复核交接。 |
| `server.py` | 在现有角色和访问控制下提供询价作业的启动、历史、刷新和执行 ID 核对接口。 |
| `quotepilot/extraction_workflow.py`、`quotepilot/provenance.py` | 复用已有复核事务，保留原生来源、执行 ID、原文引用和人工修改证据。 |
| `quotepilot/integration_status.py` | 提供独立开关与经本地核对的最近原生回执。 |
| `web/app.js`、`web/index.html`、`web/native_jobs.js` | 询价详情内的原生作业入口、平台状态和人工复核操作。 |
| `scripts/sprint_live.py`、`scripts/native_rfq_preflight.py` | 移除历史诊断脚本绕过就绪检查的写请求；补充可重复的脱敏只读诊断。 |
| `.env.example`、`Dockerfile`、`requirements*.txt` | 默认关闭可选功能，镜像包含用于核对的 DSL，声明语义比较所需的 YAML 依赖。 |
| `tests/test_native_rfq_jobs.py` | HTTP 协议夹具与真实本地业务 API、数据库、人工确认、审批及导出测试。 |
| `evidence/native-rfq-20261110/`、本文档 | 保存当前 API 实际返回、测试结果与复验步骤。 |

官方 MOI v5 参考：[创建工作流](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/data-processing/workflows/create-workflow.html) · [启动作业](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/data-processing/workflow-jobs/start-workflow-job.html) · [恢复工作流](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/data-processing/workflows/resume-workflow.html) · [节点详情](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/data-processing/workflow-jobs/get-workflow-job-node.html) · [作业结果](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/data-processing/workflow-jobs/get-workflow-job-result.html) · [计算资源类型](https://docs.matrixorigin.cn/moi/zh/5.0/guides/ai-studio/resource-center/compute.html)。
