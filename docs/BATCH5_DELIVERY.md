# 批次五交付 · 2026-11-08

接续远程1b7db3d，仅开发commercial-upgrades；登录、部署、现网备份获取及公网验收全部暂停。

## 实际代码

- 管理员运行指标API与页面：从query_turns/extraction_runs已保存响应ID去重计数，Token只用usage回执，缺失留未知；SQL修复/分析回执分别计数。没有实际单价与账单，不虚构每RFQ成本、准确率或ROI。合成测试中的receipt明确标记合成，不作为外部调用证据。
- 实际保存的查询耗时、失败/拒绝轮次、提取确认、字段改值、复核状态、分数据集导入/警告与报价计算失败计数。扫描窗口各最多10000条，并公开范围；不是覆盖平台全部账单的监控系统。
- SQLite quick_check、本地审计链、原文件大小与Schema记录；只检查本地，不探测外部平台。reviewer不能访问运行指标或整库备份。
- 幂等Schema版本登记、索引和供应商/商业报价只读投影回填。保持SQLite及原始不可变数据，未实现自动降级迁移。
- 独立合成业务链脚本：真实上传→字段证据复核→报价方案→业务审核→管理员审批→PDF/Excel→RFQ V2差异及重新询价影响→只读查询→审计→备份恢复。无网络/模型调用，不使用生产文件。
- 三分钟脚本、现有能力/未完成项和集中部署待办。原Genesis/MOI/MatrixOne代码保留，未将本地功能冒充原生API。

## 实测

初次全量pytest：237 passed、8 failed。8项均因旧合成扫描素材08_scan_manual.eml缺失；不算通过。原始缺失文件无法还原，新增明确标记的合成栅格PDF邮件替代，并在manifest保留旧SHA、登记新SHA及原因，附重建脚本。修复后全量回归：**245 passed，1条第三方Starlette/httpx弃用警告，24.85秒**；无跳过项。原始输出见evidence/batch5_pytest.txt。

- 全链脚本36次ASGI接口检查全部符合预期，包括401、403和409拒绝；真实生成PDF/XLSX并重新读取金额；审批100件快照不因V2的500件而变化；整库SHA与恢复表行数核对通过。
- 证据：evidence/business_cycle.json，包含状态、毫秒耗时、实际本地业务ID、导出文件摘要；不是公网状态或原生执行ID。
- 四个DOM套件：11+6+6+8=31条断言通过；使用模拟HTTP，未声称真实浏览器交互验收。
- 本轮外部模型、原生平台和联网搜索：均未执行。无新增收费资源，无新API Key，无线上修改。

## 完成程度与限制

| 范围 | 状态 |
|---|---|
| 字段证据、复核、变更记录与本地审计 | 本地自动化通过；任意OCR版式及外部审计锚点未实现 |
| RFQ版本、保守匹配与报价影响 | 本地自动化通过；歧义需人工确认 |
| 结构化报价、透明成本、三方案、双账户审批、PDF/Excel | 本地自动化通过；供应商字段人工结构化，汇率人工维护 |
| 可观测性/Schema/备份恢复 | 部分完成；任务级账单、自动备份、企业身份、并发容量与租户隔离未完成 |
| MatrixOne/Genesis原生深度集成 | 保留适配及历史记录；本轮没有成功原生调用证据，Snapshot等未验收 |
| 3分钟视频、真实客户案例、商用ROI | 仅完成脚本和合成案例；未录制视频，无真实客户效果或ROI |
| 部署与公网、真实联网联合分析 | 按要求暂停/仍阻塞，未算通过 |

不以单一百分比掩盖上述边界；当前可交付的是有自动化证据的本地业务闭环，尚不能标记整体商用验收或比赛原生集成验收完成。

## 文件清单

quotepilot/operations.py、store.py、security.py；server.py；web/operations.js、app.js、index.html；scripts/business_cycle.py、rebuild_scan_fixture.py；tests/test_operations.py、test_business_cycle.py、foreign_v07/08_scan_manual.eml及manifest；evidence/business_cycle.json、batch5_pytest.txt；README.md；docs/BATCH5_DELIVERY.md、DEMO_3MIN.md、DEPLOYMENT_TODO.md、ARCHITECTURE_COMMERCIAL.md。
