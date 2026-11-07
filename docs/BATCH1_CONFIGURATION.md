# 批次一配置与数据边界

## 不改变现有数据库

本批次沿用 SQLite，保留原业务表、邮件、附件、报价、管理员登录和平台集成代码。
新增 query_sessions、query_turns、external_searches、external_search_budget 记录；不修改或删除原业务记录。
AI 查询通过独立 `mode=ro` 连接、`query_only`、SQLite authorizer、SQLGlot AST 校验执行。
限定业务表/字段及函数，禁止 DDL/DML、多语句、递归、系统表、文件访问及跨库读取。
最大返回 100 行；执行阶段默认 1 秒进度中断。SQL、参数、来源、时间、模型响应 ID 保存在当前管理员会话的查询日志。
这不是多租户实现，未宣称通过多租户隔离验收。

当前线上免费服务的临时 SQLite 限制仍存在。本批次未自动迁移到 Supabase；现网未完整备份前，不用重新部署冒险覆盖现有新增数据。

## Genesis

复用 GENESIS_ACCESS_TOKEN / GENESIS_API_KEY、GENESIS_BASE_URL、GENESIS_MODEL_ID、GENESIS_API_STYLE，设置 QUOTEPILOT_PROVIDER=genesis。
所有密钥仅存于后端环境，不放入源码、网页、测试证据或 Git。
复杂 SQL 规划采用最高 4096 输出 Token；模型输出截断、超时或验证失败时返回失败状态，不执行未通过校验的 SQL。
结果分析单独调用模型，结论附结果行引用；引用和数值校验失败会保留真实查询表格，并明确标注 AI 分析不可用。
四个快捷查询直接只读查库，不调用模型。

## 外部搜索

优先配置 Tavily Basic，官方文档当前列明每月 1000 免费 Credit、Basic 每次 1 Credit，无需信用卡：
https://docs.tavily.com/documentation/api-credits
https://docs.tavily.com/documentation/api-reference/endpoint/search

后端环境变量：

- QUOTEPILOT_SEARCH_PROVIDER=tavily
- TAVILY_API_KEY（现有免费账户的密钥）
- QUOTEPILOT_SEARCH_ENABLED=1
- QUOTEPILOT_SEARCH_FREE_TIER_CONFIRMED=1（须先确认账户免费套餐及关闭自动超额计费）
- QUOTEPILOT_SEARCH_DAILY_LIMIT=20（代码硬上限 20 次/日，上海时区；可调低，不能借此调高）

可替换适配器：QUOTEPILOT_SEARCH_PROVIDER=brave，使用 BRAVE_SEARCH_API_KEY。适配器不代表已开通 Brave 免费套餐或可免费使用。
未配置密钥/未确认免费额度时返回 blocked。不会自动开户、购买额度、升级套餐或改成收费请求。
Tavily 固定 basic，不启用自动参数或高级搜索；失败请求同样占应用本地每日尝试预算，避免无限重试。
搜索词单独输入；联合模式不会自动把整份内部结果、客户名和内部价格当搜索词发送。

每条结果保存提供方、URL、标题、摘要、检索时间及可用的发布日期。链接未检查时显示 not_checked；不能冒充链接验证成功。
公开价格始终标为 public_reference_only，不是正式供应商报价、实时库存或采购承诺。

## 联合分析

内部价格、外部参考价格须对齐件号、规格、单位、件状和币种；日期缺失、字段不一致或来源不可追溯时，不计算价差。
外部字段须逐项出现在所引用原文片段中。仅提取搜索摘要能明确支持的信息，不猜测 EA、币种或日期。
现有库没有真实成交订单表。真实成交价问题先澄清，不能用报价草案或采购成本替代。
当前供应商示例价格缺少单位/规格；即使取得网页参考价，也可能只能展示“不可直接比较”。

## 可复现验证

Python 回归测试见 tests/test_query_center.py、tests/test_search_joint.py、tests/test_center_api.py 及既有测试。
前端 DOM 测试使用 jsdom@26.1.0，模拟 HTTP，不代表真实浏览器或真实模型调用：
`NODE_PATH=/path/to/jsdom/node_modules node tests/query_center_ui.cjs`
真实模型验收：将已有 Genesis Key 安全放入进程环境后运行：
`PYTHONPATH=. python scripts/accept_batch1.py`
测试只使用官方模拟素材的隔离 SQLite；不会写现网数据库。失败尝试保存在 attempt_history，不覆盖为成功。
