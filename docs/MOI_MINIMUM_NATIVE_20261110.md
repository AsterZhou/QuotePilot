# MOI 单节点部署对照与执行前验收

2026-11-10 15:11–15:20（上海时间）。开始时从 GitHub 读取 `commercial-upgrades` 的 HEAD 为 `32cf8a094495d17de176ddf6dd96c3c4f29b88dd`。当前记录补充同日 14:13 的诊断。工作区为 `ec94c942-2d64-c6be-c968-e793caaef007`。本轮没有修改 QuotePilot 业务代码。

**部署通过，执行尚未授权。** 同一工作区、令牌和单节点定义，缺少绑定字段的部署默认值，真实返回 disabled、version 0、底层 ID 为空。补齐默认值，真实返回 ready、version 1、非空定义与版本 ID。另一次全新创建复现了完整默认值首次提交即可 ready。无法据此推断旧四节点实际运行一定成功。

## 平台操作

[脱敏 HTTP 记录](../evidence/native-minimum-20261110/records.json)中的每个对象包含操作标签、时间、方法、URL、HTTP 状态、平台追踪号和响应。创建、重新部署的请求体以及失败业务体完整保留。目录、身份、规格等成功列表按相关字段摘录。时间是客户端收到响应的 UTC 时间。

| 对象 | 平台操作与结果 | 核验 |
|---|---|---|
| 旧 RFQ 工作流 `45e246b6-9a6f-5331-82cd-44c00f67cb18` | 带凭据读取详情和作业列表；最后再次读取详情 | 两次详情一致。disabled、触发器关闭、无 run 操作，执行数 0。未修改 |
| A · 固定输入 `a1f75c37-eb9d-57ce-bfe3-6debdf2142c3` | 从平台内置模板 8 提取单个 moi:extract v1 节点。以原生支持的 documents.content 传入指定合成询价，保留模板 n_to_1 方式，声明件号、数量、单位、件状的输出结构。一次 POST workflow-deployments | ready，版本 1，底层定义 `c838d9bc-2c52-4ffc-8156-2d5811983c8e`，版本 `774142a5-6e06-434f-9786-6301d73b2823`；GET 复核有 run；作业列表 0。保留手动 one_shot 供获批后单次验证 |
| B · 参数对照 `0776b8fc-2041-5693-91ed-c9167e75a5d0` | 在同一模型节点的合成文件标识使用 .vars.run_ref，建立与旧工作流相同的必填字段冲突。首次只给 run_ref 默认值 | HTTP 200 / OK，同时 disabled、version 0、两个底层 ID 为空。详情显示第二个必填字段 vars_run_ref 绑定到 vars.run_ref |
| B · 原 ID 重新部署 | 用官方 POST workflow-deployments 指定已有测试 workflow_id；原 DSL、表单和运行方式不变，仅补齐 default_values.vars_run_ref，值与 run_ref 相同 | HTTP 200 / OK，ready，version 1，底层版本 `a3d42a63-3a83-430b-bb4c-23fbc0c048cf`。零次执行，完成对照后暂停，GET 核验 paused |
| C · 首次保存对照 `a6f498d2-f79f-5c85-aa92-0bb469564635` | 新对象首次提交即同时提供两项默认值，复用 B 的同一 DSL 与表单 | ready，version 1，版本 `c9343f43-d69b-4978-bb01-eefef4fea442`。零次执行，暂停并核验 paused |

A 的部署请求追踪号为 `7d2a54a6-fcda-44b8-8950-b6d62a139f91`。B 的缺省值请求与修复请求分别为 `85ec2b9a-f7bb-441d-8a80-e4dd1742450e`、`e2f35901-0ca5-4c92-b00c-c5ac9dd7aca0`。这些标识用于追踪 HTTP 请求，执行 ID 仍为空。

## 保存、启用与启动

本轮使用官方 v5 接口 `POST /workflow/v2/workflow-deployments`；新建时省略 workflow_id，针对已有测试对象重新部署时提供该 ID。一笔成功 HTTP 返回可以对应两种实际结果：有定义记录但没有可执行版本，或已有可执行版本。以随后的 GET 详情、触发状态及平台版本 ID 为准。所测 one_shot 定义在参数完整时即进入 ready，没有另行调用 enable。官方文档没有把 version 0 定义为唯一错误码；本轮实验只解释了所复现的情形。

历史产品客户端在启动时才对齐两个字段，同时要求工作流已经 ready。该实现保护了运行请求，却无法修复部署阶段缺失的默认值。旧定义实际保存的默认值只有 run_ref。历史 resume 用于 paused，对当时的 disabled 不适用；本轮没有向旧定义发送启动、恢复或重新部署请求。控制台仍显示“验证码发送服务异常，请稍后重试”；未观察到登录后的页面请求，不把文档中的操作顺序当成抓包结果。

已对照现有仓库 DSL、部署/诊断记录、内置文档提取模板和工作区实际算子目录。原 SQL v1 的 sql、rows、affected_rows 以及 LLM v3 的 prompt、text、model、输出 text 等能与目录匹配。模板使用 .vars、.state 和 save 表达式；旧 SQL 插值、Base64、运行时保存路径、表权限和原生模型路由仍需真实运行。最小实验使用 moi:extract v1；其输入没有指定 Genesis 后端的 model 字段。A 待验证的目标值是 PN-0001、3、EA、FN，当前没有模型节点输出。

## 身份、资源与费用

- 工作区列表包含指定 ID。当前有效角色为系统 superadmin，原工作流对象的 owner 为同一角色。真实的独立工作流创建、重新部署、启用、暂停均有成功记录。角色权限详情额外读取返回 404，工作区作为对象读取权限视图返回 422，工作区单项 GET 返回 405；不能将这些响应推导为 workflow.run 被拒绝。IAM schema 列出 workflow.create/manage/run、compute_resource.create/use 等独立操作。创建实例或执行作业的实时授权仍未用写请求验证。
- 当前可见实例列表两次为 []；目标定义详情未返回明确计算资源绑定。三种启用的 task 规格分别为 6、12、24 Credit/小时，三种 query 规格均未启用。规格管理权限为 false，无法说明新建或使用实例的授权。共享或默认运行资源能否承载实际执行尚未验证；无需可见专有实例，已能让本次单节点工作流就绪。SQL 与非 SQL 计算实例类型需分别核对。
- 工作区可选模型接口返回 HTTP 200、models=[]；独立 Genesis 模型目录 HTTP 200，返回 10 项。模型通道和可能的默认路由尚未经执行验证。原生算子的提供方 go-worker 指算子实现，不能据此判定推理提供方。
- 官方 Billing 账户入口按文档传 X-API-Key，返回 HTTP 401，错误码 invalid_producer_api_key，完整业务体在证据中。未取得可验证的计费账户 ID，因此无法继续用该接口核实账户设置、账户明细、可用赠送/充值余额、到期与适用范围。历史截图显示 Genesis 和 AI 服务用量，不能证明本次执行可用赠送额度。可见的 task 小时价也不会自动成为某一笔模型节点的价格。
- 本轮未发送 POST /executions，未调用模型推理、执行 SQL、创建或启动计算实例、改动计费设置。账户净 Credit 变化无法读取核对。A 是等待后续授权的一次性定义，没有定时或动态服务；B/C 已暂停。没有需要停止的新增计算实例。

## 下一步与预算边界

只针对 A 的首次真实作业，申请**仅使用现有 Credit、现金 0、额外实例 0、最多一次提交、零自动重试**。独享实例预算为 0 Credit。平台未给工作区抽取槽位的单价、内部调用次数、单作业价格或硬上限，不提供伪精确报价。建议授权上限 1 Credit，作为允许支出的上限，不是实测或平台报价。若该金额不能由平台保障，保持待运行；不得把单次提交、超时、发送取消请求或暂停定义视为金额上限。实际费率、计费取整、赠送到期、暂停/删除后的结算尾差仍需在有计费账户权限的页面核对。暂停 API 面向 ACTIVE 计算实例，应另读回状态；这次没有创建实例。

预算与零现金条件可验证后，在当前 A 的详情和执行列表复核 ready 与无其他运行，仅 POST 一次，保存 execution_id。轮询同一 ID，并核对 root.extract_fields 的输入输出、模型渠道、状态及四个字段；状态未知先核对作业列表。仅在这一步通过后再引入 SQL、执行独立写回，以及接回 QuotePilot。旧工作流的修复候选是以同一合成引用补齐部署默认值，在隔离副本验证。

官方参考：[创建与编排](https://docs.matrixorigin.cn/moi/zh/5.0/guides/ai-studio/processing/workflow/create-and-edit.html) · [内置信息提取案例](https://docs.matrixorigin.cn/moi/zh/5.0/guides/ai-studio/processing/workflow/templates/document-extraction.html) · [部署](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/data-processing/workflows/create-workflow.html) · [可选模型](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/agents/model-configurations/list-available-models.html) · [Billing 当前账户](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/genesis/billing/accounts/current.html) · [暂停计算实例](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/resource-center/compute-resources/suspend-compute-resource.html)。
