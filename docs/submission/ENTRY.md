# QuotePilot 报价室｜比赛提交文字

**赛道**　企业命题 · RFQ 询价分析与报价智能体

**作品介绍**　QuotePilot 面向企业采购与工业零部件报价团队，处理询价邮件、PDF 和 Excel 原件。MOI 原生四节点工作流读取询价原文，使用 Genesis 将自然语言需求整理为带原文证据的候选字段，业务人员核对后，系统匹配供应商规格、价格、交期与起订量，按确定性规则计算成本。客户变更数量时，系统定位受影响报价，保留旧版，经业务复核和管理员审批后导出金额一致的 PDF 与 Excel，并可将已审批快照写入 MatrixOne 后读回校验。

**技术实现**　系统使用 Python、FastAPI 和 SQLite 管理业务状态。MOI 原生工作流编排 MatrixOne SQL 与 Genesis 模型节点，按同一运行引用读取原文、提取字段、写入候选并读回。应用独立查询并核对原文证据；Decimal 引擎根据已确认条件核价。双角色签核后，服务端按报价编号与版本写入完整快照，读回载荷并重新计算 SHA-256。

**工程验证**　公网验收记录四个原生节点完成、独立 SQL 查询匹配、双角色签核和同版 PDF / Excel 金额一致。技术说明附原生执行及快照回执和 2026 年 11 月 10 日发布验收范围。

**应用价值**　采购人员可以从报价明细追溯原始文档、字段修订和供应商条件；客户更新需求后，按版本识别受影响的报价并保留原审批依据。

**数据合规**　公开材料均展示虚构客户、合成邮件、合成供应商价格及审批记录。仅限合成文件，演示价格不代表实际供应商报价或交易。

## 评审表单链接

| 表单项目 | 填写内容 |
|---|---|
| 可运行智能体 | https://quotepilot-matrixnext-final.onrender.com/ |
| 演示视频 | https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/video/ |
| 说明文档 | https://quotepilot-matrixnext-final.onrender.com/guide/technical.html |

管理员访问码为 `QP-Judge-Admin-26M`，业务复核员访问码为 `QP-Judge-Review-26M`。访问码与合成样例列于快速上手指南，技术说明末节提供入口。无需注册。完整源码位于 AsterZhou/QuotePilot 的 final-submission 分支，仓库按既有权限访问。
