# QuotePilot v0.6.0 实际接入验收 · 2026-11-05

结论：Genesis 真实提取 → 人工确认入库 → Decimal 核价 → 审批 → Excel 导出通过；MOI 工作区及 SQL 可访问，已确认报价快照可写入 MatrixOne 并读回校验。业务主库仍为 SQLite；这不是全表迁移，也不是 AI Studio 原生工作流已经上线。公网部署没有完成，外部客户端完整报价无法验证。

## 实际执行记录

| 项目 | 已执行结果 | 证据（项目 evidence/live_20261105） |
|---|---|---|
| Genesis 模型列表 | HTTP 200，实际列表含 qwen3.8-flash / responses 能力 | models_probe.json |
| 第一次真实模型提取 | 两条合成英文自由正文需求；PN-0001 数量3、EA、FN；GSK-001数量2、EA、件状null；没有生成价格 | first_live_extraction.json |
| 真实 HTTP 完整链路 | 入库前0行；未明确确认返回409；确认新增2行；重复确认幂等；PN单价16.63、3件49.89；GSK缺价空白；数据库/CSV/XLSX一致 | live_smoke_result.json，genesis_quote.csv/xlsx/json |
| 真实浏览器闭环 | 上传EML、真实模型提取、复核表单、入库、待核价对照、审批、XLSX下载；无页面JS错误；下载金额49.89 | browser_live_result.json，browser_live_quote.xlsx，browser_live.log |
| MOI 工作区 | HTTP200，返回一个实际可访问工作区 | workspace_probe.json |
| AI Studio工作流目录 | HTTP200，返回0条；仅证明可访问列表，没有部署工作流 | moi_resources_probe.json |
| MOI Catalog目录 | HTTP200，返回default/shared目录；不能据此声称完成原生业务表迁移 | moi_resources_probe.json |
| 云端SQL | SELECT 1，异步状态success，真实读回1 | moi_select_probe.json |
| MatrixOne报价快照 | 在专用 quotepilot.quote_snapshots_v1 写入已确认的合成报价，读回payload及SHA256一致 | live_cloud_mirror.json |
| UI云端同步 | 通过页面按钮调用真实后端与云端，重复相同快照同步成功，平台页显示本库校验证据 | browser_cloud_result.json |
| 启动脚本 | 隐藏输入路径到达Uvicorn启动；另用进程环境注入密钥启动并实际HTTP检查通过 | secure_launcher_smoke.json |
| 回归 | 95通过、0失败，1条Starlette弃用警告 | unit_tests.log/xml |
| 综合验收门禁 | 官方素材组30通过、合成/接口契约组65通过；新增格式验收17/20；总体退出1，competition_ready=false | 项目evidence/verification.json，verification_gate.log |

上述真实模型网络调用共执行三次，均为合成自由正文变体，不构成泛化准确率或吞吐性能评估。前两次记录 usage.total_tokens 为1107与902；第三次浏览器调用没有单独采集usage。不推算完整费用或宣称所有调用token总量。真实企业客户邮件/生产订单测试：未执行。新增附件文字上下文读取已编码，但没有对真实模型执行复杂Excel/PDF泛化验收，不能把正文用例通过外推为附件已全部通过。

云端快照示例：报价 `QP-771C05221452` v2，SHA256 `7d65cdb2692eb172a07d45d36503754b90e7198939883f7589920738461223e9`。快照保存为规范JSON的Base64及摘要，保留完整字段；不是可直接按物料分析的规范化业务行表。本次未将原邮件上传云端。数据库及表是实际创建的；没有预置虚假成功标记。

## 对应实现与可复现命令

| 实现 | 文件 / 函数 | 验证 |
|---|---|---|
| Responses与Chat接口封装、结构/证据校验 | quotepilot/providers.py / GenesisProvider.extract | tests/test_genesis_workflow.py；真实调用证据 |
| 来源文字、建议持久化及人工确认 | quotepilot/extraction_workflow.py / source_context, create_run, confirm_run | 未确认不入库、幂等、修改保留原建议、Mock拒绝入库等测试 |
| HTTP入口 | server.py / extract_stored_email, confirm_extraction, sync_approved_quote | 真实HTTP脚本、浏览器脚本 |
| MOI异步SQL、快照读回校验 | quotepilot/moi_sql.py / MOISQLClient.execute, mirror_quote, sync_quote | tests/test_moi_sql.py六项契约测试；真实云端及UI读回 |
| 历史连接证据呈现 | quotepilot/integration_status.py / integration_status | 新库不会继承别处的已接入状态；平台页不是持续在线心跳 |
| 启动与密钥输入 | scripts/start_secure.py | secure_launcher_smoke.json |
| 核价/审批/导出 | quotepilot/pricing.py，reviews.py，exports.py | 原有回归＋真实HTTP和浏览器下载金额核对 |

项目目录运行：

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/verify.py
python scripts/start_secure.py --workspace YOUR_WORKSPACE_ID
```

`pytest`预期95通过。`verify.py`包含仍未修复的格式验收，当前预期退出1，不能删掉失败项使结果变绿。此离线命令不会再次调用收费模型。真实云端证据是本次另行执行的运行记录，不是离线测试伪造的网络返回。

在隐藏提示输入密钥，打开 http://127.0.0.1:8765。具体操作见README“启用真实Genesis与云端快照”。工作区ID使用你自己的工作区；本次账号已验证的ID为 `ec94c942-2d64-c6be-c968-e793caaef007`。也可仅运行 `python scripts/start_secure.py` 使用Genesis，云端快照功能则需配置工作区。密钥不会写入源码、日志、浏览器或交付包；退出后不保存密钥。

交付包根目录 live_20261105/ 下保存实际执行脚本（从解压根目录运行，使用安装项目依赖的Python）。这些验收脚本读取标准输入密钥，不是普通用户启动入口。浏览器验收额外需要Node的playwright及Chromium；脚本使用开发环境的浏览器路径，其他机器须自行指定适用路径。只运行产品不需要Node或浏览器自动化工具。

## 部分完成与未完成

- **已编码并有真实网络验证**：Genesis自由正文提取、显式人工采纳入库、报价闭环、MOI SQL查询、已确认报价的云端镜像与读回。
- **已编码但未验证泛化**：AI上下文的最多5工作表Excel、10页文字PDF读取；不支持扫描OCR，公式拒绝，不静默截断超限输入。不能将其视作复杂附件解析验收通过。
- **仍是规则模拟能力**：分析页四种SQL白名单问法，无自由NL2SQL。默认Mock明确标注且不允许以真实模型结果入库。
- **仅本地契约/迁移设计**：integration/moi_operator.py及完整业务表迁移SQL；云端Python算子、规范化RFQ/成本/供应商表读写尚未部署。
- **尚未开发/上线**：AI Studio工作流编排与运行、平台Agent发布、公共HTTPS入口、企业身份认证、多租户、ERP实时同步、通用扫描件OCR。
- **独立格式验收仍失败**：多工作表确定性Excel解析、横向PDF、扫描PDF。该20例是冻结后的合成输入，已在早期验收使用，本次是回归；不能称本次又找了20份陌生第三方素材。详细原因在evidence/format_acceptance.json。
- **公网部署**：只有本机loopback浏览器验证，没有外部URL。外部无开发环境的完整报价测试：未执行，当前无法验证。

云端错误处理曾实际触发一次：DDL成功后错误请求结果集收到404；已修改为仅SELECT/SHOW/WITH读取结果集，随后真实建表、写入、读回及UI复测通过。失败证据 live_cloud_failure.json 保留，不能把初次失败删去。

## 11月11日截止前工程顺序

1. 11月6日：先保证当前受限报价闭环可稳定重放；落地有服务端密钥和访问控制的HTTPS演示入口，并从另一台设备完成上传、提取、确认、核价、导出验收。通过标准是外部实际操作成功，不是仅获得一个URL。
2. 11月6–8日：在MOI AI Studio部署能实际执行的询价提取/核价工作流，保存自己的运行ID、失败分支与写表查询证据；将成本/价格读写纳入平台核心路径。当前镜像不足以替代此项。未验证的Python执行权限按实际账户检查。
3. 11月8–9日：优先修复多工作表和横向文字PDF，补充未参与开发的输入回归；扫描件来不及完成时保留明确人工处理分支，不冒充已支持。
4. 11月9日：冻结版本，重跑95项回归、格式门禁、真实模型和外部客户端测试，所有失败保留。
5. 11月10日：仅录制已通过的路径；更新180秒脚本的旧“未接入”旁白，清楚区分已连接模型/云端镜像与原生工作流。11月11日留提交缓冲，不在截止前扩大功能范围。

## 官方接口依据

- Genesis SDK与鉴权：https://docs.matrixorigin.cn/moi/zh/5.0/developer/quickstart/genesis/openai-sdk.html
- 实际模型列表：https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/genesis/models.html
- Responses：https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/genesis/text-generation/responses.html
- MOI HTTP与工作区鉴权：https://docs.matrixorigin.cn/moi/zh/5.0/developer/quickstart/ai-studio/http-api.html

Genesis采用Bearer令牌，MOI采用X-API-Key与X-Workspace-ID。本账户同一令牌的这两类访问已分别实测成功，不能将旧文档记录中的“凭据不能互用”当作当前事实；其他账户仍需检查实际授权。代码固定MOI官方API地址，不猜测SDK方法。
