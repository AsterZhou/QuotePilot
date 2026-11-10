# QuotePilot 发布验收

2026 年 11 月 10 日，北京时间。测试文件均为合成数据，所有新增交易进入独立的演示或验收数据库。

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



| 检查 | 运行环境 | 观测结果 |
|---|---|---|
| 完整回归 | Python 3.12，SQLite，隔离测试库 | 272 项通过。1 条第三方 Starlette / HTTPX 弃用提示 |
| 前端打包 | 无框架静态前端 | JavaScript 语法、HTML 依赖与自托管字体引用通过，生成 dist/web |
| DOM 交互 | jsdom，模拟接口 | 商业报价 8、查询 11、证据复核 6、版本差异 6，共 31 条断言 |
| 浏览器业务链 | Chrome Headless Shell，真实本地 HTTPS | 20 步，114 条 API / 鉴权响应。上传、三家供应商、审核、审批、双格式下载、版本影响均通过，复核员访问管理指标返回 403 |
| 移动布局与进程重启 | 390 像素视口，真实本地 HTTPS | 来件、证据、版本、商业报价、审计五页均无页面横向溢出；上传一封新邮件，停止并重启后端，沿用同一 SQLite 文件可查到该邮件 |
| 服务内交易与备份 | ASGI 接口，真实 SQLite，无外部模型 | 36 次接口检查。未审批导出被拒、已审批原单保留 100 件、审计链有效，哈希校验后的备份可恢复 |
| 真实 AI | 本地 FastAPI 调用线上 Genesis | 提取 HTTP 200，qwen3.8-flash，899 Token。EX-768EC06ECA39，响应 resp_157ebb4d-81b6-9e2f-bd25-1977f357464e。复核后新增 1 行 |
| 真实云数据库 | 本地 FastAPI 调用线上 MatrixOne | 已审批 CQ-8463E589EDD44CCF / v3，业务写入及整份载荷读回通过。最后查询 01a1c452-934f-7638-a000-e894cd1730e4 |
| 正式导出 | 本地浏览器下载，独立文件读取 | 本轮 100 件报价 PDF、Excel 合计均为 1,378.00 元；演示中的 500 件报价两种文件合计均为 6,880.00 元 |
| 成片 | 导出文件与公开播放器 | 原中文字幕演示为 180.000 秒、1920×1080、24 fps，全片可解码。另有 175 秒录屏和 87 秒无声产品短片 |

## 前一公网版本的验收

外部 Chrome 从独立 Render 公网地址登录两个角色，实际执行 28 步操作，页面记录 154 条鉴权及业务响应，未捕获的前端异常为零。匿名业务请求返回 401，复核员访问管理员指标返回 403。执行版本为 `e88342a`。

| 检查点 | 公网实测 |
|---|---|
| AI 需求提取 | 自然语言邮件经真实 Genesis 取得 `EX-DDB11C307C9B`，本次 773 Token。业务人员对照原文确认 PN-0001、100 EA 后入库 |
| 供应商 | 上传三页合成 PDF，解析三家报价并逐条核对；生成三种方案 |
| 移动端 | 公网 390 像素视口下进入收件、证据、版本比较、报价与审计五个页面，页面内容宽度均为 390 像素，无未捕获异常 |
| 原需求 | 两角色签核，`CQ-2C36E387C95442F5` 保留 100 件、1,378.00 元，PDF 与 Excel 读回一致 |
| 新需求 | 版本差异识别 100 → 500 及关联旧报价。重新核价、审核、批准后，`CQ-9B967EA9DFA345A7` 为 500 件、成本 5,502.00 元、报价 6,880.00 元，两种导出均核验通过 |
| 云端快照 | 两个已审批版本都从工作台写入真实 MatrixOne 并完整读回。对 500 件审批版本重复同步，仍为同一报价编号、版本与摘要 |
| 重启后的状态 | 专门上传的临时来件在独立服务重新部署后清除；镜像中的两封合成来件恢复，管理员与复核员继续可登录。未将本地临时磁盘作为持久存储 |

各项测试验证不同边界。浏览器测试使用的本地 HTTPS 地址与外部平台 API 地址分别记录；测试数据与企业实际采购数据相隔离。
