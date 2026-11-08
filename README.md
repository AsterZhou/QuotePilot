# QuotePilot · 商业闭环开发分支

2026-11-08：第二至第五批开发在独立 `commercial-upgrades` 分支推进，**未部署；现网服务及数据未修改**。下方v0.7/批次一内容属于历史记录，不能视为本轮线上状态。

已新增字段证据与人工复核、RFQ版本差异、供应商原件及结构化复核、透明成本和三方案、双角色审批、PDF/Excel及运行指标。测试使用赛事样例与明确合成数据；供应商字段和汇率目前人工维护，未实现个人SSO、多租户或完整原生平台验收。

- [第二批交付](docs/BATCH2_DELIVERY.md) · [第三批](docs/BATCH3_DELIVERY.md) · [第四批](docs/BATCH4_DELIVERY.md) · [第五批及限制](docs/BATCH5_DELIVERY.md)
- [可复现全链记录](evidence/business_cycle.json) · [三分钟脚本](docs/DEMO_3MIN.md) · [架构](docs/ARCHITECTURE_COMMERCIAL.md)
- [集中部署待办](docs/DEPLOYMENT_TODO.md)：所有登录、部署、现网备份获取、公网及原生平台验收待以后集中处理。

```bash
python -m pytest -q
python scripts/business_cycle.py --output tmp/business_cycle.json
```

第二条仅使用临时SQLite和合成文件，禁用赛事自动播种，不调用外部模型或网络；ASGI TestClient结果不等于公网验收。

---

# QuotePilot · 报价室 v0.7.1

## 批次一：AI 查询中心（独立分支验收）

新增 Schema 检索、业务术语、独立只读 SQLite、SQLGlot AST/字段/函数校验、会话追问、澄清及带证据引用的 AI 分析。保留原四个快捷统计与所有业务页面。外部搜索为 Tavily/Brave 可替换适配器，未配置 Key 时明确阻塞；联合参考价对齐拒绝缺失单位/规格/币种的记录。当前未迁移数据库，也未覆盖现网部署；验收状态以 docs/BATCH1_ACCEPTANCE.md 为准。

配置与复现：见 docs/BATCH1_CONFIGURATION.md。此处为批次一历史状态；后续开发见文首。


## 2026-11-07 工作台可用性更新

首页四项统计可打开对应明细：邮件、全部需求、历史询价、供应商价格。新增历史/价格/成本的只读检索、分页、完整字段详情和原始工作簿下载；来件标记赛事示例或后续导入。平台接入页展示当前服务实际配置及本数据库成功记录，未启用 Genesis 时不再显示可执行的 AI 提取按钮。管理员访问控制保留，无公众注册。

当前公网仍为 Free + 临时 SQLite，Genesis 仍为 Mock；尚无 Supabase 连接与持久化迁移。本轮没有配置新密钥、购买资源或宣称原生工作流成功。开发环境历史真实调用与当前线上配置分开呈现。

2026-11-07 免费演示：https://quotepilot-demo.onrender.com 。管理员密码仅保存在 Render 服务环境变量 `QUOTEPILOT_LOGIN_PASSWORD`，无公众注册。Free实例不挂持久盘，休眠、重启和重部署会丢失上传、报价和审计数据；仅使用赛事/合成文件，及时下载导出。当前公开实例使用明确Mock，不调用Genesis，不代表MOI原生工作流成功。

公网HTTP闭环验收：`python scripts/accept_free_deployment.py --url https://quotepilot-demo.onrender.com`，通过记录见 `evidence/free_deployment/result.json`。Supabase尚未连接或迁移；现有9个文件84处数据库调用依赖SQLite，迁移涉及SQL方言、自增ID/返回值、事务以及附件BLOB改私有对象存储，需单独验证。

面向报价专员的RFQ处理工作台。输入EML及Excel/PDF附件，保留原文件，提取需求，匹配价格，执行Decimal规则，人工复核，审批后导出Excel并可镜像至MOI云端。

**当前验收：受限本地闭环与真实Genesis/MOI报价镜像通过；Render Free临时演示已上线（SQLite不持久化），MOI原生工作流未运行成功。** 不具备完整参赛验收通过结论。详见[本次验收报告](docs/ACCEPTANCE_V07.md)。

## 历史记录：2026-11-06上线准备（以下状态为当日记录）

源码已建立本地Git基线tag v0.7.0；GitHub远程备份仍待账号授权，不能将本地SHA当成已推送版本。Render适配见deploy/RENDER.md；付费模板deploy/render.paid.yaml尚未应用，创建前必须由账户所有者确认价格。Docker构建流程见.github/workflows/container-acceptance.yml，仅手动触发；目前没有真实构建成功记录。公网URL仍未产生。

本轮修改限于PORT、Render公共Origin、运行时secret读取、构建/持久化验收脚本及交付文档。MOI最新只读诊断与可发送官方支持的问题说明见docs/MOI_SUPPORT_REQUEST_20261106.md。2026-11-05的disabled与空实例列表为历史事实；2026-11-06相关读取多返回503，当前状态不能沿用旧记录冒充最新读取。

## 启动

Python 3.11+，本次使用3.12。首次安装需要联网；离线规则报价不需要Key。

```bash
python -m venv .venv
# Linux/macOS:
.venv/bin/python -m pip install -r requirements-tested.txt
.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8765
```

Windows将`.venv/bin/python`替换为`.venv\Scripts\python.exe`。打开 http://127.0.0.1:8765 。首次自动从`workspace/samples`建立SQLite：6封官方模拟邮件、300条需求、249条历史明细/94组RFQ、163条成本、342条供应商资源。素材来自赛事模拟数据，不是真实客户业务。重复启动不重复导入。

启用真实模型：

```bash
.venv/bin/python scripts/start_secure.py --workspace YOUR_WORKSPACE_ID
```

在隐藏提示粘贴Genesis个人令牌，仅保留在进程环境；交付包不含密钥。工作区不需要时可省略`--workspace`；需要同步云端报价时须填写自己的真实ID。模型使用本次真实列表验证可用的`qwen3.8-flash`及Responses API。`.env.example`只是说明，不会自动加载。

## 实际操作

1. 进入询价来件，导入`evidence/v07/tls_live/input.eml`（合成自由正文）。重复导入不重复新增记录。
2. 选择邮件，点击**Genesis补充提取**。这会显式提交文字并消耗模型额度。对照原文逐行核对字段；未知件状保持空白。填写RFQ号、复核人、说明，明确勾选后入库。Mock不会冒充真实调用，也不能采纳为真实模型结果。
3. 选择PN-0001、GSK-001，设基准日`2026-09-20`、加价率20%。PN-0001/FN/3EA为49.89；GSK-001无可靠价格保持待核价。含缺价的整份报价不能审批。
4. 本次变更留痕验收将PN数量从3改为4，原建议和人工字段同时保留，对应金额66.52。这是合成测试的显式变更，不代表模型原文数量是4。
5. 仅选可核价行，生成草案；核对单位、件状、交期、税费、来源，填写复核人和说明后审批。XLSX/CSV/JSON读取保存快照；已确认版本不随底层成本变化。
6. 点击**同步MOI云端快照**，服务端写入专用表并读回核对SHA256。主库仍为SQLite，不代表规范化业务表全部迁移。
7. 扫描PDF或不支持版式：查看解析提示，点击**人工补录**。下载核对原文件，填写页码/单元格定位、需求字段、复核人和原因，再明确确认。系统标记人工来源，不将其写成AI提取；定位由人工填写，没有自动核验。
8. `tests/foreign_v07/01_multi_business.eml`演示多工作表；`05_geometry_pdf.eml`演示横向PDF；`04_formula.eml`展示公式拒绝；`08_scan_manual.eml`转人工处理。

注意：报价示例使用历史基准日；不能将其宣传为今天的可执行供应商承诺。供应商原表缺少单位等条件，系统仍要求人工复核。税费运费未自动计入。

## 测试与真实记录

```bash
python -m pytest -q
python scripts/foreign_v07.py
python scripts/verify.py
python scripts/demo.py
```

- 回归：122通过，0失败，1条第三方弃用警告。
- 历史固定格式验收：19/20；扫描件自动提取仍失败，所以`verify.py`预期返回1，competition_ready=false。没有移除旧失败用例。
- 新的冻结后合成陌生文件：10/10，包含正常解析及应拒绝/转人工的场景。它不是第三方生产数据或独立人工审计。
- 生产模式本地HTTPS完整HTTP验收：真实Genesis、复核变更、缺价拦截、导出与云端读回通过。证据`evidence/v07/tls_live/result.json`明确`external:false`；不是公网浏览器验收。
- 云端原生工作流：定义存在但disabled，启动/恢复HTTP400；可见计算资源列表为空，没有execution_id。失败证据保留。

部署后从另一机器运行：

```bash
python scripts/accept_deployment.py --url https://YOUR_ACTUAL_DOMAIN
```

需要演示登录密码，实际发送合成询价并调用真实服务；无Mock。浏览器完整操作仍须独立验证。离线pytest与verify不会调用模型，也不会假装网络已经验证。

## 公网部署参考（当前在线状态见文首）

以下缺少托管权限等描述为此前本地阶段的历史限制；当前免费公网版本已上线，仍未完成持久化和线上真实模型接入。

[deploy/README.md](deploy/README.md)提供Dockerfile、Compose、Caddy HTTPS、数据库持久化卷、运行时secret挂载和初始化/部署脚本。当前缺少兼容Python容器运行的服务器/托管权限、域名，且本环境没有Docker。**Docker构建、公网URL、外部浏览器闭环均未验证。** 不会把仅前端可见页面当成真实部署。

生产版为带密码的单团队演示空间，登录后操作；API与文件下载均需会话。不是企业SSO、多租户或RBAC。不要上传真实敏感业务数据用于公开演示。

## MOI原生工作流

`integration/rfq_native.yaml`使用实际工作区目录返回的WorkItem ID和版本，依次云端读RFQ→平台模型→保存待复核建议→读回。平台已保存定义ID `45e246b6-9a6f-5331-82cd-44c00f67cb18`，但未成功执行。云端合成输入已写入并读回验证，原生模型输出为空，不能声称原生提取通过。没有新建付费计算实例。

```bash
python scripts/workflow_status.py --workspace YOUR_WORKSPACE_ID --workflow YOUR_WORKFLOW_ID
```

该命令读取真实状态；不自动购买资源或生成成功标记。可在服务器环境配置`MOI_WORKFLOW_ID`后通过平台页面明确查询状态。后续须先获得可用任务计算资源并处理disabled，再用同一工作流ID继续，不重复新建定义。

## 目录

```text
server.py                       FastAPI与HTTP入口
quotepilot/security.py           生产模式、登录、会话、Origin校验、限额
quotepilot/parsing.py,xlsxio.py   EML/横向与官方PDF/多工作表Excel
quotepilot/manual_intake.py      来源约束的人工补录及幂等
quotepilot/providers.py          显式Mock / 真实Genesis建议
quotepilot/extraction_workflow.py 人工采纳、原建议、入库审计
quotepilot/pricing.py            Decimal核价与异常规则
quotepilot/reviews.py,exports.py  版本、审批、Excel/CSV/JSON
quotepilot/moi_sql.py            云端报价镜像及SHA256读回
quotepilot/native_workflow.py    真实工作流状态与就绪检查
web/                            中文工作台
deploy/                         独立容器HTTPS部署配置
integration/rfq_native.yaml     已保存、尚未成功运行的原生DSL
tests/                          官方组/合成组/新陌生文件
scripts/                        启动、验收、陌生输入、离线演示
evidence/v07/                   本次日志、真实网络回执、导出
docs/                           验收、实际架构、180秒脚本
```

旧v0.5/v0.6文档及证据仅作历史记录。以当前README、ACCEPTANCE_V07及v07证据为准。不存在客户端、收入、节省工时或泛化准确率结论。

# 批次一收尾进度

本轮修复和真实复测记录见 [docs/BATCH1_CLOSEOUT.md](docs/BATCH1_CLOSEOUT.md)，整库备份与恢复边界见 [docs/SQLITE_BACKUP.md](docs/SQLITE_BACKUP.md)。现网备份尚未取得，未覆盖部署。

