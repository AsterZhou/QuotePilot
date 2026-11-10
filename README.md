# QuotePilot 报价室

面向企业采购和工业零部件报价团队的 RFQ 询价分析与报价智能体。上传客户来件与供应商报价，从原文核对、成本核算、版本对比一路走到双角色审批和 PDF、Excel 正式交付。

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



**客户把 100 件改成 500 件时，原报价还能发吗？** 合成案例 PN-0001 中，旧单价直接放大得到 6,890 元，重新分摊固定费用后的正式金额为 6,880 元。报价室可以定位变更、保留旧单，并将新金额追溯到供应商原件与审批记录。

| 评审材料 | 入口 |
|---|---|
| 评委工作台 | [登录合成演示环境](https://quotepilot-matrixnext-final.onrender.com/) · 角色访问码见技术白皮书第八节 |
| 产品演示 | [真实操作录屏与中文字幕](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/video/) |
| 技术白皮书 | [网页阅读](https://quotepilot-matrixnext-final.onrender.com/guide/technical.html) · [仓库版本](docs/TECHNICAL_DOCUMENTATION.md) |
| 验收依据 | [最终测试报告](docs/submission/ACCEPTANCE.md) |
| 提交文字 | [作品介绍、技术亮点与应用价值](docs/submission/ENTRY.md) |

## 工作台

- **询价与复核**　EML、PDF 和 XLSX 原件留存。规则解析与 Genesis 候选提取共用证据复核路径，修订有记录。
- **供应商核价**　逐项检查规格、币种、件状、有效期、交期与 MOQ，比较最低成本、最快交付及平衡方案。
- **版本与审批**　登记客户需求的新版本，定位受影响的报价。业务复核员审核，管理员批准，两种导出读取同一版本。
- **存储与追溯**　SQLite 保存业务主记录，MatrixOne 接收已审批快照，并读回校验载荷与 SHA-256。

## 运行与测试

Python 3.12、FastAPI、SQLite、PyMuPDF、openpyxl、原生 JavaScript。使用项目根目录下的独立 Python 环境运行以下命令。

```sh
python -m pip install -r requirements-tested.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8765
```

开发运行仅绑定本机。正式演示使用 Docker、生产鉴权和独立的数据库路径。登录、模型与数据服务通过服务端环境变量注入，配置名称见 [.env.example](.env.example)。回归入口为 `python -m pytest -q`。前端静态资源随镜像分发，无需编译框架依赖。

## 数据说明

演示使用合成询价与供应商数据。供应商候选为规则解析，Genesis 辅助处理非结构化来件；核价由 Decimal 规则执行。报价导出后由业务人员自行交付。
