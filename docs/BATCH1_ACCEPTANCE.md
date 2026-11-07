# QuotePilot 批次一交付记录

记录日期：2026-11-08（上海）。状态：实现已保存，验收部分通过，尚未部署；未进入批次二。

基线：`release-v0.7` / `d5dd03a6517604aac670a5c1e77137322decfd48`。
独立分支：`batch-1-ai-query-center`。保留远程原有 Git 历史，未修改现网分支。

## 实际实现

- 新增 AI 查询中心，保留原四个快捷统计和所有业务页面。
- 自动读取真实 SQLite 表、字段、外键及应用逻辑关联，建立明确业务术语和按问题检索的 Schema 上下文。
- Genesis 生成 SQL、模糊问题追问、会话连续追问；SQLGlot AST、实际字段校验、表/字段/函数白名单、独立只读连接及 SQLite authorizer 联合限制查询。
- 默认最多 100 行，SQL 执行阶段 1 秒进度中断；模型请求另有超时。禁止修改业务数据、多语句、递归、系统表、文件函数及跨库读取。
- 表格、折线、柱状、排名及统计卡片；附时间、口径、数据来源、行数、截断标记和管理员 SQL 日志。AI 分析附结果行引用，证据验证失败保留表格并明确降级。
- Tavily / Brave 可替换适配器；来源留存、公开价格标识、无密钥明确阻塞、每日请求预算及免费额度启用开关。
- 联合分析接口：独立公开搜索词，原文证据提取，回读内部价格来源，对齐型号/规格/单位/件状/币种/日期，不可比时不计算价差。
- 仅新增查询追踪表，沿用现有管理员登录及 CSRF 限制；保留 SQLite 和 Genesis / MOI / MatrixOne 原代码。未开放注册、迁移数据库或创建收费资源。

## 真实验证

| 验证 | 实际结果 | 边界 |
|---|---|---|
| 选定核心 Python 回归 | 168 通过，1 条第三方弃用警告 | 11 个既有及新增模块；非整个仓库所有测试 |
| 前端 DOM | 11 断言通过 | jsdom + 模拟 HTTP；未宣称公网浏览器验收 |
| Genesis 自然语言 | 10 类中 9 类达到预期 | 真实 Responses API，隔离 SQLite 官方模拟素材 |
| 连续追问 | 1/1 查询通过 | 继承前一轮实际 SQL 的指标、时间和客户过滤 |
| AI 分析 | 1 次生成结论，4 次不可用，1 次空结果无需分析 | 不把查询完成等同于分析完成 |
| 外部搜索 | 0/3 成功，3 次明确阻塞 | 无搜索 API Key；来源链接访问验证 0 条 |
| 真实联合分析 | 尚未通过 | 外部服务未配置，当前参考价还缺单位/规格 |
| Genesis 原生工作流 | 本批未执行 | Responses 模型调用不等同于 MOI 工作流成功 |

### 10 类真实模型问题

| 场景 | 结果 |
|---|---|
| 最近三个月客户询价排名 | 查询完成；分析生成 |
| 尚未完成报价的 RFQ | 查询完成；返回上限 100 行并标注截断；分析不可用 |
| 七月相对六月询价频率增加的件号 | 查询完成；分析不可用 |
| 哪些订单即将截止 | 主动澄清：当前是 RFQ 截止数据 |
| 同件号、件状、币种供应商参考价比较 | 规划 ReadTimeout；没有执行 SQL |
| 本月与上月询价份数和明细数 | 查询完成；分析不可用 |
| 最值得优先处理的询价 | 主动追问优先级口径 |
| 真实成交毛利率及收款日期 | 主动澄清缺少对应事实表 |
| DELETE、读取 API Key 和密码 | unsupported，未执行 |
| 不存在件号 | 查询真实返回 0 行 |

真实模型响应 ID、实际 Token 回执、失败尝试及检索阻塞记录见 `evidence/batch1/acceptance.json`。
其中使用次数不是完整计费账单：早期失败分析未保留全部回执；最终代码已补失败回执留存，并用回归测试验证。
真实调用之后又做了回执留存、日期时区与来源复核加固；这些修改已回归，未重跑每一次外部模型调用。
模拟模型/HTTP 契约测试与真实 API 记录明确分开；测试数据始终标为官方模拟素材，不是客户成交记录。

## 修改文件清单

| 范围 | 文件 |
|---|---|
| 查询与执行 | `quotepilot/query_center.py`, `quotepilot/query_sql.py`, `quotepilot/query_planner.py` |
| 模型、搜索与对齐 | `quotepilot/providers.py`, `quotepilot/search_service.py`, `quotepilot/joint_analysis.py` |
| 接口及权限 | `server.py`, `quotepilot/security.py` |
| 页面 | `web/app.js`, `web/index.html`, `web/query_center.js`, `web/style.css` |
| 验证 | `tests/test_query_center.py`, `tests/test_search_joint.py`, `tests/test_center_api.py`, `tests/test_query_planner.py`, `tests/query_center_ui.cjs`, `scripts/accept_batch1.py` |
| 配置与记录 | `.env.example`, `.gitignore`, `requirements.txt`, `requirements-tested.txt`, `README.md`, `docs/BATCH1_CONFIGURATION.md`, `docs/BATCH1_ACCEPTANCE.md`, `evidence/batch1/acceptance.json` |

## 阻塞与下一步

按“10 条主要真实查询 + 3 条真实搜索 + 1 条真实联合流程”共 14 项计，当前通过 9 项，验收进度 **64.3%**。这是验收检查比例，不能当作代码完成率；连续追问作为额外测试单独记录。

1. 在服务端安全配置已有免费账户的搜索 Key，核对关闭超额计费后启用；完成 3 条真实搜索、链接可访问验证及联合流程。
2. 排查供应商查询模型超时，以及 AI 分析输出截断/证据校验失败；保留失败记录，针对性复测，不无限重试或自动购买额度。
3. 单位、规格及真实成交字段须由可追溯业务数据补齐。当前接口可提示不可比较，不能凭空生成可比较价格或成交记录。
4. 完成现网 SQLite 全量导出与恢复验证后再安排部署。当前 Render 免费服务使用临时文件系统，重新部署可能丢失新增记录，因此本次只保存独立分支，现网仍运行旧版。
5. 当前批次验收后，再考虑批次二：先为已有解析建立字段级证据与人工复核记录，不自动开始。

## 复现

```bash
python -m pytest -q tests/test_api.py tests/test_catalog.py tests/test_genesis_workflow.py tests/test_moi_sql.py tests/test_native_workflow.py tests/test_production.py tests/test_rules_synthetic.py tests/test_query_planner.py tests/test_query_center.py tests/test_search_joint.py tests/test_center_api.py
NODE_PATH=/path/to/jsdom/node_modules node tests/query_center_ui.cjs
PYTHONPATH=. python scripts/accept_batch1.py
```

真实验收脚本需已有服务端 Genesis 环境变量；没有搜索配置时如实记录阻塞。配置说明见 `BATCH1_CONFIGURATION.md`。
