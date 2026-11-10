# QuotePilot 报价室

[打开评委工作台](https://quotepilot-matrixnext-final.onrender.com/) · [技术白皮书与角色访问码](../TECHNICAL_DOCUMENTATION.md) · [合成样例](../submission/samples/)

## 公网报价验收 · 2026 年 11 月 10 日

独立 Render 服务在合成订单上完成整笔报价。管理员上传三件阀件的询价，MOI v3 读取原文、调用 Genesis、写入候选并读回。业务复核员逐项核对原件并确认三家供应商报价，从三个方案中选择最低成本方案。另一账户完成审批。每件采购价 10 元，加工成本共 3 元，其他费用共 2 元。成本合计 **35.00 元**，三件正式报价 **43.74 元**。

| 评委可核对的记录 | 本笔公网交易 |
|---|---|
| 原生执行 | `61191015-edc2-4005-a5c7-6d6f8372d413`，四节点 completed，模型提取用时 6 秒 |
| 独立查询与复核 | MatrixOne 查询 `01a1c4d2-affd-73ce-9f81-948fac2a01bd`，字段建议 `EX-F4342754A7C6`，对照邮件后采纳 |
| 已审批报价 | `CQ-57F5B5C4DD5240BF`，v3，PDF 与 Excel 独立解析均为 3 EA × 14.58 元 |
| 已审批快照 | MatrixOne 完整载荷读回一致，最后查询 `01a1c4d3-26f7-74ea-8d8a-b588d807c0ac` |
| 验收范围 | 两个真实浏览器会话完成上传、原生作业、复核、比价、审批、同步和下载。页面记录 101 条 HTTP 回执。匿名 API 返回 401，复核员访问管理指标返回 403。281 项 Python 回归与 31 条 DOM 断言通过。 |

[下载同型合成询价](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/samples/rfq-native.eml) · [供应商报价原件](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/samples/suppliers.pdf) · [查看原生执行](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/native-v3/native.json) · [复核界面](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/native-v3/00-genesis-evidence.webp) · [正式 PDF](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/native-v3/approved.pdf) · [报价 Excel](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/native-v3/approved.xlsx) · [审批快照回执](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/native-v3/matrixone-user-receipt.json)



### 四节点 MOI 原生工作流 v3

管理员在「询价来件」中选中合成邮件，点击「AI 自动整理客户询价」，确认使用合成文件后启动，刷新处理进度并打开建议。服务端为每封询价生成独立引用。原生 SQL 节点读取 MatrixOne 中对应的原文，Genesis 模型槽位提取件号、数量、单位和件状，第三个节点写入候选字段，第四个节点读回结果。QuotePilot 再次独立查询，核对模型实际输入、字段证据和结果后，才将候选送入人工复核。

隔离 HTTPS 验收执行 `84f79f23-01ac-4d3f-a5e8-4ef600f677c8` 的四节点均为 completed。模型槽位解析为 kimi-k3，提取 PN-0001、3 EA、FN。独立读回查询为 `01a1c46c-b590-7bf0-ab50-094681cc4c8e`。两家供应商比价后，三件采购价共 30 元，加工费 3 元、其他费用 2 元，总成本为 35.00 元。按目标毛利率 20% 核价，单价舍入为 14.58 元。两种角色签核后，PDF 和 Excel 均为 43.74 元。已审批 v3 快照读回 SHA-256 为 `61a68e69169c064e4e58741748c9676607dee44a397a1214432516fede01bbbc`。

该记录中的来件、启动和采纳由浏览器完成，核价、双角色审批和导出通过业务 API 完成。评委可在工作台查看自己发起的作业 ID，并用一份新合成邮件独立复演。

