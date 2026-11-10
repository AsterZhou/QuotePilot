# QuotePilot 技术白皮书

MatrixNEXT 2026 · 企业命题「RFQ 询价分析与报价智能体」

工业零部件报价员收到一封询价邮件和三家供应商的报价，需要同时答复客户两个问题：多少钱，何时能交？QuotePilot 用 Genesis 从来件中提取带出处的需求，经人工确认后，按供应商条件计算可交付的报价方案。每个售价都能追到供应商原件，每次批准都对应一个可独立核验的版本。

## 一笔报价，两个交付选择

客户询购 3 件 PN-0001 阀件，规格为 Synthetic valve spec A，件状 FN。三家合成供应商分别承诺 20 天、2 天、7 天交货。在相同数量、费用和目标毛利率下，报价员可向客户说明：**三件总价从 43.74 元提高到 62.49 元，承诺交期从 20 天缩短到 2 天。提前 18 天的报价差额是 18.75 元。**

| 选择依据 | 选中的供应商 | 三件客户报价 | 供应商承诺交期 |
| --- | --- | --- | --- |
| 最低成本 | SYN-Cheap | ¥43.74 | 20 天 |
| 最快交付 | SYN-Fast | ¥62.49 | 2 天 |
| 成本与交期各占 50% | SYN-Fast | ¥62.49 | 2 天 |

同一供应商可以满足两种选择依据。本次批准了最低成本方案。下文用这笔合成订单说明原件如何进入模型、规则如何产生报价，以及第三方如何复核交付结果。[询价原件](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/samples/rfq-native.eml) · [供应商原件（PDF）](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/samples/suppliers.pdf) · [已批准报价（PDF）](https://quotepilot-matrixnext-final.onrender.com/guide/evidence/approved.pdf)

## 从询价原文到可采纳的需求

一封邮件可能同时包含多个件号、数量和件状。即使模型正确摘录了“3 EA”，这段引用也可能属于另一行。QuotePilot 把原文位置、模型建议和人工确认值分别保存，报价使用已确认的需求。

| MOI 原生工作流 v3 | 本笔询价的数据 |
| --- | --- |
| 读取原文 · MatrixOne SQL | FastAPI 为来件生成独立的 run_ref，保存原文及 SHA-256。SQL 按该引用读取本次输入。 |
| 提取字段 · Genesis | 从原文提取件号、数量、单位、件状及引用片段；本次模型节点耗时 6 秒。 |
| 写入候选 · MatrixOne SQL | 将模型输出写回同一引用下的记录。本次写入 1 条候选。 |
| 读回结果 · MatrixOne SQL | 原生节点读回候选。应用随后独立查询并比对结果，形成可供复核的字段建议。 |

FastAPI 使用 Pydantic 校验结构，并检查数量及引用片段。业务人员对照原件确认字段关系，记录修订和依据。遇到启动响应丢失时，服务端按原来的 run_ref 核对平台执行，再恢复对应作业。[四节点执行回执](https://quotepilot-matrixnext-final.onrender.com/guide/evidence/native.json) · [字段复核画面](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/native-v3/00-genesis-evidence.webp)

## 为什么最终报价是 43.74 元

供应商 PDF 由规则解析，业务复核员确认原件。系统检查件号、规格、单位、件状、起订量、有效期、汇率及指定交期，保留候选被排除的原因。合格供应商进入排序，金额由 Python Decimal 计算。

| 可复算步骤 | 最低成本方案 |
| --- | --- |
| 采购与费用 | 3 件 × 10.00 元采购单价 ＋ 3.00 元加工费 ＋ 2.00 元其他费用 ＝ **35.00 元总成本**。样例运费与税率均为零。 |
| 单件售价 | 35.00 ÷ 3 ÷（1 − 20% 目标毛利率）＝ 14.5833… 元；按 ROUND_HALF_UP 舍入到分，得 **14.58 元**。 |
| 正式报价 | 3 件 × 14.58 元 ＝ **43.74 元**。PDF 与 Excel 均取已批准版本的单价与数量，报价单各行可直接加总。 |

**综合方案为何也选择 SYN-Fast？** 引擎逐行计算「0.5 × 候选总成本 / 最低总成本 ＋ 0.5 × 候选交期 / 最短交期」，取较低分。本例最快供应商的成本为 50 元，评分约 1.21；7 天供应商成本为 41 元，评分约 2.34；20 天供应商成本为 35 元，评分为 5.50。三份原件都参与了选择。多行订单在选定候选后按采购金额权重分摊批次运费，并以分为单位处理尾差。[供应商条件](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/samples/suppliers.pdf) · [方案核价画面](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/native-v3/03-cost-plans.webp)

## 客户改量后，原审批依据如何保留

客户更新询价时，系统保存新的 RFQ 版本，标识增删改项、待人工匹配的歧义项及受影响的报价。每份报价保留计算时采用的需求、供应商条件和费用。业务复核员审核、管理员批准时，服务端同时检查角色与预期版本。

另一次独立公网验收中，客户需求从 **100 件改成 500 件**。原已审批报价仍为 **1,378.00 元**；新需求重新核价并经两种角色签核，生成 **6,880.00 元**的新报价。采购团队可查到两份报价各自依据的数量和批准记录，继续处理变更时也能向客户解释差额。[版本变更验收报告](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/acceptance/)

## 架构与数据职责

| 系统层 | 技术与工程职责 |
| --- | --- |
| 原件与交互 | 原生 JavaScript、Python 邮件解析、PyMuPDF、openpyxl 处理 EML、文字 PDF 和多工作表 Excel；保留原件、正文片段、页码或工作表行号供复核。 |
| 业务服务 | Python 3.12、FastAPI、Pydantic、Uvicorn；服务端执行会话鉴权、字段校验、状态转换和角色审批。Docker 部署于独立的 Render 演示服务。 |
| 模型与规则 | MOI v3 在平台内编排 Genesis 与 MatrixOne SQL。模型负责从非结构化文字提出候选，确定性规则负责资格检查、成本与交期排序、金额舍入。 |
| 主库与查询 | SQLite 保存来件、字段修订、报价及审批事件。分析查询经 SQLGlot 校验语法树和表列范围，在独立只读连接中执行。 |
| 文件与云端复核 | 已批准版本生成 PDF 和 Excel。应用以「报价编号、版本」为键写入 MatrixOne 快照，读回完整载荷并重算 SHA-256；连接恢复后可按原键重试。 |

四节点工作流处理**询价字段**。签核完成后的应用同步处理**已批准报价**。两条路径各有回执，下表可分别核对。

## 公网验收与原始证据

2026 年 11 月 10 日，两个独立浏览器会话使用合成数据，经过真实公网工作台、Genesis 和 MatrixOne，完成同一笔三件订单。下列执行编号和报价编号属于这次存档；演示录屏使用同型样例独立运行，编号随运行生成。

| 要核对的问题 | 这次运行的结果 | 原始材料 |
| --- | --- | --- |
| 工作流是否在 MOI 上执行？ | 执行 `61191015-edc2-4005-a5c7-6d6f8372d413`，4 个节点全部完成，应用独立读回匹配。 | [执行回执](https://quotepilot-matrixnext-final.onrender.com/guide/evidence/native.json) |
| 业务流程是否连通？ | 上传询价后，复核 1 条需求、确认 3 家供应商，生成 3 种方案，由两种角色完成签核和下载。记录含 101 条 HTTP 响应。 | [逐步验收记录](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/native-v3/result.json) |
| 客户收到的两个文件是否一致？ | 报价 `CQ-57F5B5C4DD5240BF`，v3，已批准。两份文件均为 PN-0001、3 EA、单价 14.58 元、合计 43.74 元，交期 20 天。 | [正式 PDF](https://quotepilot-matrixnext-final.onrender.com/guide/evidence/approved.pdf) · [同版 Excel](https://quotepilot-matrixnext-final.onrender.com/guide/evidence/approved.xlsx) |
| 云端是否保留了同一批准版本？ | 读回完整载荷并校验摘要，回执标记 verified；可按报价号、版本和查询编号对应原单。 | [快照回执](https://quotepilot-matrixnext-final.onrender.com/guide/evidence/matrixone-user-receipt.json) |

该次发布通过 **281 项 Python 回归测试、31 条 DOM 断言**。匿名业务请求返回 401，业务复核员访问管理员指标返回 403。历史固定格式文件验收为 **19/20**，无文字层的扫描 PDF 保留原件，由人工补录和复核。测试数描述工程覆盖范围；生产语料准确率与实际人工作时收益有待现场测量。

演示环境面向单团队，使用合成数据。实例重置后临时业务数据可能清除，本文所引的报价与回执已独立存档。评委可用合成样例自行复演，两个角色的访问码和上传顺序见操作指南。[打开工作台](https://quotepilot-matrixnext-final.onrender.com/login) · [访问码与操作指南](https://quotepilot-matrixnext-final.onrender.com/guide/#login)
