# QuotePilot 报价室

面向企业采购和工业零部件报价团队的 RFQ 询价分析与报价智能体。上传客户来件与供应商报价，从原文核对、成本核算、版本对比一路走到双角色审批和 PDF、Excel 正式交付。

**客户把 100 件改成 500 件时，原报价还能发吗？** 合成案例 PN-0001 中，旧单价直接放大得到 6,890 元，重新分摊固定费用后的正式金额为 6,880 元。报价室可以定位变更、保留旧单，并将新金额追溯到供应商原件与审批记录。

| 评审材料 | 入口 |
|---|---|
| 产品演示 | [真实操作录屏与中文字幕](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/video/) |
| 技术白皮书 | [网页阅读](https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/) · [仓库版本](docs/TECHNICAL_DOCUMENTATION.md) |
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
