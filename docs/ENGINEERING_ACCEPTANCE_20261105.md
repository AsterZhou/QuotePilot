> 历史版本记录：以下结论对应 v0.5 / v0.5.1。v0.6 已新增真实 Genesis 与 MOI SQL 报价快照接入，当前状态请先看 [LIVE_INTEGRATION_20261105.md](LIVE_INTEGRATION_20261105.md)。历史记录中的“未连接”不能代替最新结果。

# QuotePilot 严格工程验收 · 2026-11-05

**结论：受限的本地报价流程通过；完整 RFQ 产品、外网部署与平台集成验收未通过。**

原版 v0.5 的“63 项测试通过”可以复现，但这证明的是已有样例与已有测试断言；不能证明通用文档解析、真实模型能力、企业系统接入或公网可用。本次在代码冻结后加入新输入，确实复现了错误和缺失，并交付 v0.5.1 修复版。没有把缺失能力改称“已设计完成”。

## A. 验收对象和测试来源

- 基线为已交付 `QuotePilot_v0.5_Verified.zip`。字节数2730143，SHA256：`1dc5ad0bca8b1ab5ae7c5d26dd5ad9c5a9bed47f688925720afc0f4261c88e43`。逐文件对比 .py/.js/.css/.sql/.html 与验收开始时工作区代码一致，无代码差异。
- 当前候选为 v0.5.1；原基线没有覆盖写入。新 ZIP 内保留基线 ZIP，以便复现修复前结果。
- 本次重新创建独立 Python 虚拟环境，按 `requirements-tested.txt` 安装依赖。初始系统环境缺少pytest，首次测试未能执行；安装完成后重新完整执行，以下成绩来自新日志。
- 官方数据为赛事提供的**模拟业务素材**，不是实际企业客户数据。原有“official”测试组的意思是使用这些文件，不能理解成第三方官方认证。
- 新输入20个，含8个邮件正文类、6个Excel附件类、6个PDF附件类；另保留附件独立二进制。它们全部是**本次验收新建的合成文件**，在修复前固定预期及SHA256，未参与 v0.5 开发。没有伪称第三方真实邮件。
- 同一批文件修复后回放已经属于回归验证，**17/20不是盲测准确率**。第三方真实客户邮件/表格/PDF泛化测试：**未执行**。没有人工真值全集、性能基准或真实业务耗时指标。

## B. 本次实际运行结果

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 原版测试 | 63通过、0失败；1条Starlette弃用警告 | `evidence/baseline_tests.log`、`baseline_junit.xml` |
| 新输入在原版回放 | 6满足预期、14不满足 | `foreign_baseline.json`、`.log` |
| 修复版测试 | 81通过、0失败；1条Starlette弃用警告 | `candidate_tests.log`、`candidate_junit.xml` |
| 全量验收命令 | `python scripts/verify.py`实际退出1；81项回归通过，格式验收仍有3失败 | `full_gate.log` |
| 同批新输入在修复版回放 | 17满足预期、3仍失败；独立验收命令退出码1 | `foreign_candidate.json`、`.log`、`foreign_candidate_exit.json` |
| 真实HTTP本地闭环 | 新邮件导入1行，重导新增0行；建议单价16.63，3件49.89；确认后的数据库JSON、CSV、XLSX金额相同 | `http_acceptance.json`、`http_quote_snapshot.json`、`http_quotation.*` |
| 不认识的件号 | `UNSEEN-2026`返回待核价，单价留空 | `http_acceptance.json` |
| 歧义表头导入 | 原文件保留，0条可靠需求，`status=needs_review`及原因明确返回 | `http_acceptance.json` |
| JavaScript语法 | `node --check QuotePilot/web/app.js`退出0 | 本次执行记录 |
| 浏览器完整交互 | Playwright启动失败：Chromium可执行文件缺失；测试主体**未执行** | `browser_attempt.log`；不能复用上次浏览器记录作为本次通过证据 |
| 外部互联网客户端报价 | **未执行；无法验证** | 没有已部署公网URL，未发起外部浏览器验收 |
| Genesis / MOI / MatrixOne真连接 | **未执行；没有已连接证据** | 无可用环境凭据；代码边界见F节 |

81项测试包含原63项、17个新解析回归及1个跨客户审批拦截回归。它们不涵盖仍失败的三类解析；独立格式验收保留失败，不将失败排除后冒称全部验收通过。没有统计代码覆盖率。

## C. 已完成：可运行能力与对应实现

以下函数均可在交付源码定位。行号索引见 `evidence/function_index.json`。测试命令在QuotePilot目录执行；这些命令的测试均包含在本次81项完整运行中，不另外伪称每条命令都曾独立执行。

| 功能 / 真实边界 | 文件、函数 | 可重跑的测试命令 | 本次结果 |
|---|---|---|---|
| 标准MIME邮件头、正文、附件；官方HTML表格、XLSX、指定文本PDF模板 | `quotepilot/parsing.py:parse_eml/parse_pdf/normalize_line`；`xlsxio.py:read_xlsx` | `python -m pytest -q tests/test_api.py -k 'inbox or preview'` | 原6封/300行及来源断言通过；陌生格式结果单列D节 |
| 确定表头别名、结构化key:value正文、标题行后的表头 | `fields.py:canonical/validate_headers`；`parsing.py:parse_eml`；`xlsxio.py:read_xlsx` | `python -m pytest -q tests/test_acceptance_regressions.py` | 17个受支持/安全拒绝回归通过；不是任意自然语言解析 |
| SQLite邮件/来源/询价主信息/明细/成本/价格/报价/审计持久化 | `store.py:open_db/ingest_eml/seed_official/audit` | `python -m pytest -q tests/test_rules_synthetic.py -k 'dedup or source_bytes or bad_row or message_id'` | 重导幂等、跨询价保留、冲突拒绝、原始字节/字段证据通过 |
| 精确件号、件状、单位、MOQ、有效期、库存与汇率检查 | `pricing.py:supplier_issues/quote_line/batch_quote` | `python -m pytest -q tests/test_rules_synthetic.py -k 'expired or future or incomplete or fx or stock or uom or condition or moq or cost or quantity'` | 过期、缺价、缺汇率、非有限数、库存差额、单位及件状不符等断言通过 |
| Decimal加价、毛利和金额舍入 | `pricing.py:strict_decimal/calc_unit/money` | `python -m pytest -q tests/test_rules_synthetic.py -k 'exact_markup_and_margin or fx_evidence'` | 成本100/加价20%=120；目标毛利20%=125；汇率来自价格行 |
| 报价保存、人工单价/件状/交期修改、凭据与版本校验、人工确认锁定 | `reviews.py:create_quote/load_quote/change_quote`；`server.py:quote/review_quote` | `python -m pytest -q tests/test_rules_synthetic.py -k 'saved_review or manual_edit or unpriced or condition_edit'` | 修改必须有依据；版本冲突及确认后再改被拒绝；仍缺需求字段编辑能力 |
| CSV/XLSX/JSON读取保存快照 | `exports.py:quote_csv/quote_xlsx/audit_json`；`server.py:saved_export` | `python -m pytest -q tests/test_rules_synthetic.py -k saved_review_exports` | 改底层价格后导出仍与保存版本金额一致；真实HTTP另核49.89 |
| 只读历史统计、四类规则问法、明确的询价/明细/件号口径 | `analytics.py:run_query/summary`；`server.py:analytics/ask/metrics` | `python -m pytest -q tests/test_api.py -k query`；`python -m pytest -q tests/test_rules_synthetic.py -k metrics` | 真SQLite查询，不是预制结果；历史249行、94组RFQ；询价金额缺失返回null |
| 操作和价格/原文件来源追溯 | `store.py:audit`；`server.py:line_detail/source_download/audit_trail` | `python -m pytest -q tests/test_rules_synthetic.py -k 'official_attachment or source_bytes or saved_review'` | 原始EML/附件哈希一致；Excel有单元格信息，PDF有模板项页码；非防篡改审计 |
| 跨客户草案不可确认为同一份报价（本次修复） | `server.py:make_quote`；`reviews.py:change_quote` | `python -m pytest -q tests/test_rules_synthetic.py -k cross_customer` | 草案可用于对照，但出现approval_blockers，正式确认HTTP409；按客户自动拆单未实现 |

## D. 独立新输入：完整成功、失败和原因

这里“通过”含正例正确提取和反例安全拒绝。以包含风险行的邮件为例，仅提取正确行但不报告丢弃行也算失败。数量0应明确拒绝，不当成已成功提取的有效需求。

| 冻结输入 | v0.5 | v0.5.1 | 修复版实际输出 / 原因 |
|---|---|---|---|
| 01_standard_html.eml | 通过 | 通过 | 实际字段与固定预期一致 |
| 02_plain_text.eml | 失败 | 通过 | 实际字段与固定预期一致 |
| 03_alias_html.eml | 失败 | 通过 | 实际字段与固定预期一致 |
| 04_duplicate_html_header.eml | 失败 | 通过 | 规范化后表头重复；拒绝覆盖数量等业务字段; 没有可靠提取的需求行；请人工录入或使用提取 Provider |
| 05_partial_missing_part.eml | 失败 | 通过 | 件号缺失；保留原始行待人工修复 |
| 06_zero_quantity.eml | 失败 | 通过 | 数量必须为正整数且不超过精确存储上限; 没有可靠提取的需求行；请人工录入或使用提取 Provider |
| 07_standard.xlsx.eml | 通过 | 通过 | 实际字段与固定预期一致 |
| 08_alias.xlsx.eml | 失败 | 通过 | 实际字段与固定预期一致 |
| 09_title_rows.xlsx.eml | 失败 | 通过 | 实际字段与固定预期一致 |
| 10_duplicate_trimmed_headers.xlsx.eml | 失败 | 通过 | 10_duplicate_trimmed_headers.xlsx: ValueError: Excel 标题规范化后重复，无法可靠映射字段; 没有可靠提取的需求行；请人工录入或使用提取 Provider |
| 11_multisheet.xlsx.eml | 失败 | 失败 | 11_multisheet.xlsx: ValueError: 多工作表文件待人工选择；当前解析器仅接受单工作表; 没有可靠提取的需求行；请人工录入或使用提取 Provider |
| 12_formula.xlsx.eml | 通过 | 通过 | 12_formula.xlsx: ValueError: 公式单元格 C2 不作为可靠询价值，请提供静态值; 没有可靠提取的需求行；请人工录入或使用提取 Provider |
| 13_template.pdf.eml | 通过 | 通过 | 实际字段与固定预期一致 |
| 14_wide_table.pdf.eml | 失败 | 失败 | 14_wide_table.pdf: 未识别表格行；待人工确认或模型提取; 没有可靠提取的需求行；请人工录入或使用提取 Provider |
| 15_long_part.pdf.eml | 失败 | 通过 | 实际字段与固定预期一致 |
| 16_wrapped_description.pdf.eml | 失败 | 通过 | 实际字段与固定预期一致 |
| 17_not_an_rfq.pdf.eml | 失败 | 通过 | 17_not_an_rfq.pdf: ValueError: 未识别可靠的 RFQ 标题；文档用途待人工确认; 没有可靠提取的需求行；请人工录入或使用提取 Provider |
| 18_scan.pdf.eml | 失败 | 失败 | 18_scan.pdf: ValueError: 未识别可靠的 RFQ 标题；文档用途待人工确认; 没有可靠提取的需求行；请人工录入或使用提取 Provider |
| 19_unknown_part.eml | 通过 | 通过 | 实际字段与固定预期一致 |
| 20_known_price_new_mail.eml | 通过 | 通过 | 实际字段与固定预期一致 |

三项仍失败，不降低预期：

- `11_multisheet.xlsx.eml`：多工作表只会拒绝，未提供选择工作表/映射后入库能力。
- `14_wide_table.pdf.eml`：横向列布局无法由现有模板状态机提取，0行并给出人工处理提示。
- `18_scan.pdf.eml`：无文字层，OCR未实现；0行并给出提示。

它们是安全地没有给出报价，但**业务提取目标仍然失败**。不能把“没有乱报”改写成“该格式已支持”。

本次已修复的实际缺陷：

1. HTML重复数量表头原本把3覆盖成300；现在规范化表头后检测歧义并拒绝，原文件及异常保留。
2. Excel `Quantity` 与 `Quantity `原本规范化后覆盖；现在在映射前拒绝重复标题。
3. 同邮件一行有件号、另一行缺件号，原来第二行无提示丢弃；现在保存拒绝行和原因。
4. 零数量原来以“已解析”进入需求；现在拒绝且保留原始证据。
5. 非RFQ PDF中的四行数字序列原本被误读为需求；现在先核对限定RFQ标题，未知文档用途转人工。
6. 增加显式中文/英文表头别名、结构化纯文本正文、30行内的表头定位；没有加入模型猜测。
7. 模板PDF扩展到长件号与限定长度的换行描述，仍不是通用表格解析。
8. 解析含异常或没有可靠需求时，导入API明确返回needs_review，前端不只提示“导入完成”。
9. 新测出的跨客户草案原本可确认；现在保留对照草案，但不允许正式确认。

## E. 部分完成和未完成：不能冒充核心能力

| 项目 | 实际状态 |
|---|---|
| SaaS页面 | 页面和API代码存在；API已测。**本次完整浏览器交互未执行**；平台接入页是说明界面，不是运行证明。 |
| AI解析 | 默认Mock返回空lines、simulated=true。真实报价并非Mock数字，但没有真实模型参与。 |
| 自然语言分析 | 关键词映射4个SQL模板，结果是真数据库结果；不支持任意问题、任意筛选或模型生成SQL。 |
| 需求异常修复 | 只能保存/显示错误；没有PATCH询价件号/数量/单位、没有新增人工确认需求行接口。quote的LinePatch只能改单价、件状、交期，不能代替RFQ修复。 |
| 成本/供应商资源接入 | 只有seed_official读固定路径；无上传预览、字段映射、确认入库API。不能证明换企业成本表就能运行。 |
| 邮件/附件范围 | 标准HTML/显式别名、结构化key:value及部分模板可运行；自由邮件叙述、多工作表、常见横向PDF和扫描件未完成。独立Excel/PDF上传到邮件接口实测HTTP415，需嵌入EML。 |
| 供应商约束 | 状态/件状/日期/MOQ/汇率等已校验；原价表缺单位只能人工确认。未实现证书要求自动匹配、独立供应商资格库。 |
| 货币和成本策略 | 输出固定CNY，供应商用该行明确汇率；库存外币不自动换算。不是任意多币种报价，也不是完整税费运费/加费用/成本来源策略引擎。 |
| 库存 | 单份报价内累计校验；无跨报价库存预留、无混合库存+外采拆单。 |
| 报价客户/行组合 | 本次补了跨客户审批阻断；自动按客户/RFQ拆单、客户主数据修正未实现。 |
| 人工审批 | 有显式确认和版本锁定，但操作人自填，没有身份认证、审批角色或金额权限。 |
| 审计 | SQLite操作日志可追溯；并非不可篡改/企业合规审计系统。 |
| 历史范围 | 仅单一官方历史表；新来件在另一区域，尚不自动合并入全部历史分析。 |
| DOCX兼容接口 | 原POST /api/quote/export/docx 会按请求再创建草案，默认客户及素材声明是演示文案；不应当作用户企业正式报价单。当前快照主路径为CSV/XLSX/JSON。 |
| 产品化部署 | 无可验证公网URL；没有面向普通用户的一键托管服务。服务端仍需Python与依赖。 |

静态接口核对与实际边界探测见 `gaps.json`。未发现成本/价格上传写接口、询价行修正接口、MOI/MatrixOne运行接口。缺失项目不计作“已设计完成”。

## F. Genesis、MOI、MatrixOne 分开验收

| 服务 | 已存在代码 | 本次实际连接 | 未执行/无法验证的内容 |
|---|---|---|---|
| Genesis | `providers.py:GenesisProvider.extract` 构造HTTP Chat Completions请求、Schema校验和原文片段检查；`server.py:extraction_preview`仅建议预览 | **没有真实连接证据**；环境无Key和模型ID；实际HTTP调用extraction返回Mock空建议。原有单元测试用httpx.MockTransport | 真实模型请求**未执行**；质量、权限、延迟、模型选择和计费**无法验证**。模型建议没有正式入库闭环。 |
| MOI / AI Studio | 接入说明；`integration/moi_operator.py:handle`本地契约函数 | **没有真实连接**；没有工作区API调用及作业ID。算子在本地测试，sdk参数没有使用 | 云端工作流、邮件归档、文件卷、Python服务、Agent运行/发布**未执行**；当前账户权限**无法验证**。 |
| MatrixOne | `integration/matrixone_schema.sql`、离线CSV导出脚本 | **没有真实连接**；实际持久化为sqlite3，没有MatrixOneRepository或连接驱动使用 | 建表、迁移、写入/SELECT回读**未执行**；改DSN不能使当前服务自动切库。 |

接口返回false本身不是连通性测试；判断同时依据真实调用结果、代码无工作区/MatrixOne调用、环境无凭据。用户其他电脑或云环境是否另行配置不在本次可见范围，**无法验证**。

## G. 部署验证

已执行的是隔离临时库 + 独立Uvicorn进程 + 真实HTTP客户端，不是仅FastAPI TestClient。流程为：上传新EML → 入库 → 原文件校验 → 核价 → 确认 → CSV与XLSX下载 → 金额对照，49.89一致。

默认启动脚本明确 `--host 127.0.0.1`。本次临时服务也只绑定loopback；同宿主接口探测返回connect_ex=101（network unreachable），这只能说明当前探测范围，**不能冒充外部互联网访问测试**。

公网URL、HTTPS和外部无痕浏览器验收：**未执行；无法验证**。没有证据证明评委仅打开链接、不安装开发环境就能完成报价，因此该验收项**未通过**。浏览器客户端理论上不需Python，但目前没有被验证可用的远程服务；源码启动成功不能代替部署成功。

未执行生产压力、长时间稳定性、多租户、角色授权、渗透或跨浏览器测试。不要根据本地成功推导生产可用。

## H. 11月11日截止前的工程优先级

官网明确11月11日提交，材料须含可运行链接、视频和说明文档：https://matrixorigin.cn/matrixnext 。本次未核实截止的具体时分，不假定23:59；内部目标为11月10日完成提交材料。

| 优先级 / 时间目标 | 要完成的实际产物与验收门槛 |
|---|---|
| P0，11/5–11/6 | 已修复的误读/丢行/跨客户审批风险完成回归；接着补询价字段修正和人工确认入库，让不支持格式能通过明确人工操作完成报价。每次修改保留原字段和审计。 |
| P0，11/6–11/7 | 成本/供应商表可导入并确认映射；用非官方件号与独立成本资源从空库完成一单，缺价不报，导出与保存金额一致。当前没有完成这项。 |
| P0，取得权限后立即，最迟11/7做阻碍判断 | Genesis至少1次真实提取，保存请求结果与字段证据，再进入核价；MOI/MatrixOne若作为参赛主架构，至少实际工作流执行和业务表写入/回读。没有权限时如实登记阻碍并核实平台要求，不继续做假接入界面。 |
| P0，11/8 | 获得评委可访问的部署URL；在独立设备/网络、未登录开发环境时导入新询价、复核并下载报价。只有这条外部流程通过才算部署完成。 |
| P0，11/9 | 功能冻结，重跑原测试、冻结陌生样例及一批新外部样例；仍失败的格式明确限制或提供可运行人工补录，不夸大支持范围。 |
| P1，11/10 | 在最终部署上录制真实闭环，完成3分钟视频、说明文档、数据合规和三项链接核验。原生能力只有有运行证据才进入宣传。 |
| 缓冲，11/11 | 仅修提交阻断问题。现在不优先做新图表、营销动效、更多界面模块或最终成片美化。 |

本次没有执行尚缺的资源导入、需求补录或公网部署；上表是剩余工程顺序，不是完成声明。

## I. 从交付包重放

根目录包含 QuotePilot 和 audit_20261105。先按QuotePilot/README安装固定依赖。

```bash
cd QuotePilot
python -m pytest -q
python scripts/verify.py
# 全量验收仍预期退出1，不要将81项回归成功误认为整个项目已验收。
cd ..
python audit_20261105/acceptance_probe.py --project QuotePilot --fixtures audit_20261105/fixtures --out audit_20261105/evidence/replay.json
# 此命令预期退出1：3类格式仍不满足需求；请查看JSON，而非忽略退出码。
python audit_20261105/http_acceptance.py QuotePilot
python audit_20261105/gap_probe.py QuotePilot
```

还原基线后可重跑修复前6/20：

```bash
python -m zipfile -e audit_20261105/baseline/QuotePilot_v0.5_Verified.zip audit_20261105/baseline
python audit_20261105/acceptance_probe.py --project audit_20261105/baseline/QuotePilot --fixtures audit_20261105/fixtures --out audit_20261105/evidence/replay_baseline.json
```

这些命令不向Genesis发送请求，不创建付费云资源，不提交比赛。HTTP验收脚本用合成测试人自动确认，不能当成真实业务审批证据。
