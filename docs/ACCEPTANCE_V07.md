# QuotePilot v0.7 工程交付验收

日期：2026-11-05（上海）。结论：本次完成部署配置、生产访问控制、多工作表/横向PDF修复、可追溯人工补录，以及新的真实HTTPS后端集成验收。**P0公网部署与P1原生工作流执行尚未通过，因此不是可公开访问的完整参赛版本。** 无公网URL，没有外部浏览器完整验收记录。

## 按优先级的实际结果

| 项目 | 实际修改文件 / 函数 | 已执行命令及结果 | 证据 | 尚未完成 |
|---|---|---|---|---|
| P0生产访问控制 | quotepilot/security.py：validate_production、DemoAccessMiddleware、signed_session；server.py中间件与healthz | pytest tests/test_production.py：8通过；最终全套回归包含这8项 | evidence/v07/production_tests.log、unit_tests.xml | 新登录页没有本次外部浏览器验收；共享演示密码，不是企业权限系统 |
| P0部署包 | Dockerfile、.dockerignore、deploy/compose.yaml、Caddyfile、entrypoint.py、init_secrets.py、deploy.sh | bash -n通过；Python编译通过；YAML解析/服务、密钥及数据卷结构检查通过 | evidence/v07/config_checks.json、deployment_environment.json | 无Docker/Podman，因此镜像构建和Compose运行未执行；无目标服务器/域名/容器托管权限，未部署公网 |
| P0完整后端流程 | scripts/accept_deployment.py；原有providers/extraction_workflow/pricing/reviews/exports/moi_sql真实实现 | 在生产模式本地HTTPS服务执行，真实Genesis、复核API、核价、审批、Excel和MOI读回通过 | evidence/v07/tls_live/result.json、server.log、quote.xlsx/json/csv | external:false；这是本地HTTPS HTTP验收，不能称外部浏览器测试 |
| P1真实平台定义 | integration/rfq_native.yaml；quotepilot/native_workflow.py；scripts/workflow_status.py；server.py状态查询入口 | 真实创建定义HTTP200；实际详情为disabled、version0；运行HTTP400；resume HTTP400；可见compute列表HTTP200空数组 | native_attempt.json、native_resume.json、compute_resources.json | 无execution_id，无原生模型输出，无完整运行结果；错误正文仅ErrParamInvalid/Bad Request，不能断定唯一根因 |
| P1云端RFQ输入 | 专用quotepilot.rfq_workflow_runs_v1 | 实际写入合成输入并读回SHA256一致；模型输出列为空 | native_source_readback.json | 平台模型、待复核建议回写节点未执行 |
| P1已有报价审计 | quotepilot/moi_sql.py的mirror_quote/sync_quote保持 | HTTPS验收产生新报价QP-2329022C5184，云端写入并读回核对摘要通过 | tls_live/result.json中的query_ids及payload_sha256 | 仍为报价JSON/Base64镜像，非业务全表迁移 |
| P2多工作表 | quotepilot/xlsxio.py：read_xlsx、ParsedRows | 逐工作表读取静态值，保留sheet/cell；说明页明确提示；修复官方Excel缺少dimension元数据的兼容问题；最终回归通过 | format_acceptance.json、foreign_v07.json、unit_tests.log | 20工作表、10000行/150列上限；复杂合并表头不保证；公式拒绝；已导入失败记录不会自动重新解析 |
| P2横向PDF | quotepilot/parsing.py：parse_pdf、_horizontal_pdf | 支持显式列名和可靠行分隔/坐标列；保留RFQ号、页码或bbox；零数量/错列转人工；原官方PDF回归通过 | 历史格式19/20；新10例10/10 | 不是任意版式通用提取；扫描PDF自动提取仍未通过，OCR尚未开发 |
| P2人工处理 | quotepilot/manual_intake.py：create_manual_line；server.py来源/补录API；web/app.js补录抽屉 | 扫描原文件保留、正整数校验、来源归属、明确确认、幂等与冲突、补录后报价均有API测试 | tests/test_manual_intake.py，unit_tests.xml | 页码与字段由人工负责，系统未自动核验；新补录界面本次未执行浏览器验收 |
| P3可复现演示与脚本 | scripts/foreign_v07.py、accept_deployment.py、原demo.py；docs/VIDEO_180S_V07.md、ARCHITECTURE_V07.md | 新陌生文件10/10；真实集成正常金额66.52、缺价审批409；三分钟窗口总计180秒 | foreign_v07.log、tls_live/server.log、demo/输出 | 无最终成片，未测实录旁白时长；公网与原生成功运行镜头不能拍成已完成 |

表内证据均位于`evidence/v07/`，固定格式门禁与新陌生语料报告另在`evidence/format_acceptance.json`和`evidence/foreign_v07.json`。真实平台执行脚本保存在交付包根目录release_07，读取标准输入密钥；业务启动无需执行这些开发验收脚本。

## 真实HTTPS验收详情

`release_07/tls_live_runner.py`在临时数据库与本机TLS证书环境启动真实Uvicorn，使用同一代码的production访问控制。`scripts/accept_deployment.py`使用受信任的本地测试CA执行HTTPS；没有关闭TLS校验，没有使用模型或云端Mock。

- 未登录API返回401，登录Cookie包含Secure/HttpOnly/SameSite=Strict。
- 导入新的合成自由正文；真实Genesis响应 `resp_9136ec7e-c946-9464-bfb9-e002dbb3712b`，模型qwen3.8-flash，usage.total_tokens=1073。仅是一条合成正文测试，不代表复杂附件质量。
- 模型建议PN数量3；验收脚本模拟明确复核，把数量改为4。保存原模型3与人工确认4；重复确认不重复入库。这里的审批人是自动验收标识，不是真实企业人工批准。
- GSK-001无可靠价，金额为空；整份审批返回409。
- 仅含PN-0001/FN/4EA，历史基准日2026-09-20，加价20%，单价16.63，总额66.52。
- 正式导出XLSX/CSV/JSON；XLSX与JSON金额和数据库报价一致。
- 云端快照SHA256为 `8f6bc5ed5fade2199958620831ae2de8500570027a1dc360cb798ff8ae0f8f5c`，读回核验通过。主库仍是SQLite。

此本地证书和临时登录凭据没有打包；真实Genesis密钥没有写入源码、日志或交付文件。代码版本号在这次集成后从0.6标签更新为0.7；后续全套回归通过。最后增加的原生状态查询属于独立只读入口，不把它当作原生工作流运行成功。

## 全部测试口径

```bash
python -m pytest -q --junitxml=evidence/unit_tests.xml
python scripts/foreign_v07.py
python scripts/verify.py
```

- pytest最终 **122通过，0失败**，一条Starlette弃用警告；37项包含官方模拟文件，85项为合成输入、契约或访问控制。HTTP契约单测中的MockTransport不计作真实平台证据。
- 原固定格式门禁：20例 **19通过、1失败**。保留扫描PDF预期自动提取的旧用例；`verify.py`退出1、competition_ready=false。
- 新陌生合成输入：冻结parser/xlsxio源码SHA256后才创建10份新文件；冻结摘要与当前解析源码一致，**10/10**。包括多表同件号同数量不同RFQ、说明页、偏移表头、公式、坐标PDF、横向不同RFQ、非法数量、扫描转人工、正文别名、损坏邮件。
- 新用例中的扫描件成功标准是“明确拒绝并可人工处理”；旧用例标准仍是“自动提取成功”。两组标准不同，不合并成虚假的扫描提取通过率。
- 第三方真实客户数据、生产报价准确率、吞吐/节省工时：未执行，无法给出相关指标。
- 本次UI浏览器完整操作：未执行；v0.6浏览器记录保留为历史证据。新功能的HTTP/API通过不能代替新UI或外部浏览器通过。

初次替换Excel读取器后5项官方回归失败，定位到部分官方文件缺少worksheet dimension元数据；修复后官方300行恢复，最终122项通过。初始失败日志regression_first.log保留。早期创建原生工作流失败状态也保留，没有删除失败或伪造execution_id。

## 平台状态与阻塞

| 能力 | 实际状态 |
|---|---|
| Genesis | 本次真实响应成功；已有本地人工复核闭环 |
| MOI SQL / MatrixOne | 合成RFQ输入、已确认报价快照真实读写并核验；全量业务表未迁移 |
| MOI原生定义 | 已保存，ID45e246b6-9a6f-5331-82cd-44c00f67cb18，状态disabled |
| MOI原生运行 | 未成功，HTTP400，无执行ID；可见计算实例为空 |
| MOI网页操作 | 当前浏览器无登录会话，只到达手机号/邮箱登录页；未提交登录表单或协议 |
| 公网应用 | 未部署，无URL；缺少兼容容器托管目标及部署权限 |

启用原生工作流还需要可运行的任务计算资源/启用条件；目前不能从通用400错误断言是哪个单独权限。没有购买、注册或新建付费资源。应在原工作流ID上继续检查，避免重复创建定义和误启动收费实例。

## 截止前剩余工程顺序

1. 取得已有容器主机或兼容托管平台的部署权限及域名，执行deploy脚本，处理真实构建/证书问题；从另一设备完成浏览器闭环。只有这一步通过才可提供公开演示URL。
2. 在实际MOI账户核对任务资源与disabled启用条件；用现有定义完成真实一次运行，保存execution_id、节点输入输出与失败记录。不得凭定义ID声称运行成功。
3. 对已支持范围稳定回归；扫描件先使用已实现的人工补录。OCR无足够时间验证时不扩展宣传范围。
4. 冻结版本并录制180秒演示；在11月11日截止前保留提交与现场访问缓冲。提交作品和对外发送消息本次均未执行。
