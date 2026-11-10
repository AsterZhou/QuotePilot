# QuotePilot 报价室

面向企业采购和工业零部件报价团队的 RFQ 询价分析与报价智能体。上传客户来件与供应商报价，从原文核对、成本核算、版本对比一路走到双角色审批和 PDF、Excel 正式交付。

## 技术架构

| 系统层 | 技术栈 | 在 QuotePilot 中承担的职责 |
| --- | --- | --- |
| 交互与服务 | 原生 JavaScript、Python 3.12、FastAPI、Uvicorn | 浏览器展示原件和候选值。服务端校验会话与角色，受理文件上传、复核和审批。Docker 镜像部署于独立 Render Web Service。 |
| 原件解析 | Python 邮件解析、PyMuPDF、openpyxl | 读取 EML 正文与附件、PDF 文字层及多工作表 Excel。保留原始文件，按来源记录正文片段、页码或工作表行号，供字段复核。 |
| 模型与编排 | MOI 原生工作流 v3、Genesis、Pydantic | 在平台内执行 SQL 和模型节点。应用端校验输出结构、字段约束和原文证据，将合格候选交给业务人员确认。 |
| 业务数据与查询 | SQLite、SQLGlot | SQLite 保存来件、字段修订、报价状态和审批事件。分析查询使用独立只读连接，执行前检查 SQL 语法树、表和列的允许范围。 |
| 价格与文件 | Python Decimal、PyMuPDF、openpyxl | 以十进制定点舍入规则核价；从同一已批准版本生成 PDF 和 Excel，分别记录导出格式、版本与文件摘要。 |
| 云端记录 | MatrixOne SQL、SHA-256 | 为原生工作流保存输入及提取结果；另以报价编号和版本保存已审批快照，支持对整份载荷的独立读回。 |

[技术说明与原始运行回执](https://quotepilot-matrixnext-final.onrender.com/guide/technical.html#verification)

| 评审材料 | 入口 |
|---|---|
| 评委工作台 | [登录合成演示环境](https://quotepilot-matrixnext-final.onrender.com/) · [角色访问码](https://quotepilot-matrixnext-final.onrender.com/guide/#login) |
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
