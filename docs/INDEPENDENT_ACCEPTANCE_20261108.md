# 独立环境验收与修复 · 2026-11-08

仅修改commercial-upgrades开发分支；正式站点、SQLite、密钥、部署和原生平台均未操作。没有创建收费资源。所有新增案例为明确合成数据。

## 取回与旧扫描文件恢复

验收起点为远程9e37e47，完整清单395个文件/15072392字节。使用已连接GitHub按固定Commit取回文件，复用缓存时逐个比对Git Blob SHA。普通git clone需要交互凭据，未要求用户登录。大于1MB的Contents读取返回空内容，三个大文件从2026-11-06备份恢复后校验Git SHA，最终395项全部与远程清单一致。源码清单见evidence/independent/source-manifest.json。

新建.audit-venv，按requirements-tested.txt重新安装，无复用旧Python包目录。修复前原分支全量245 passed、1条第三方弃用警告（29.22秒）；原始输出baseline-pytest.txt。

旧08_scan_manual.eml原文件实际仍在历史仓库/旧备份中。上轮把本地下载不完整误判为原件不可恢复，并替换了素材；这个处理不妥，已有报告补上本次更正。现从旧备份恢复9731686字节原件：

- SHA256：edd691ee697e77d207c87b49ca1ce4292716e29727d7b5542c2ccded7423419a，与历史manifest一致。
- Git Blob：fc16bc87abe6ff5f3efe9fc8ac4bf1ed61d988db，与6273ad4中的原文件一致。
- 小扫描件保留为独立11_scan_small.eml，不再覆盖08；重建脚本也只写11。
- 原扫描件与人工补录专项18 passed。仍明确扫描PDF自动提取失败，转人工；未声称实现OCR。

## 实际修复

1. 旧PATCH /api/quotes/{id}在生产权限模式下仍允许单账户approve，绕过新双角色流程。现在拒绝新的旧接口正式审批并指向商用报价闭环；旧试算、编辑、草稿导出与已审批历史快照保留。开发模式旧单账户规则测试保留，不得作为生产审批使用。
2. reviewer证据页错误调用管理员审计接口而403；改为展示权限说明，完整审计仍仅管理员能查看。reviewer来件页也不再调用受限集成详情，导航隐藏无法使用的管理页面。服务端限制始终保留。
3. 审批后归档列表显示旧状态；现在刷新列表及审批详情。商用报价基准日改用服务端当前日期，避免旧演示基准日误拒当前供应商报价。手工核对表单折叠，自动提取后再展开。
4. 单行运费与整票运费显式区分。line保持旧行为；shipment须给supplier+shipping_group，选中明细按采购金额权重分摊一次，最大余数法精确到分、同余按line_id稳定分配；同批次金额/币种/汇率冲突拒绝计算。未标运输批次的旧数据不擅自合并运费。
5. 各采购/加工/运费/税费/其他成本先ROUND_HALF_UP至分再相加，销售单价至分后乘数量；毛利率按入账成本计算。小金额舍入为0阻塞审批，避免除零及假毛利。三方案仍是逐行启发式，整票运费在选择后分摊，不承诺供应商组合全局最低。

## 供应商原件自动提取闭环

新增本地可替换解析模块：有明确标签的TXT/文字PDF、带字段表头的XLSX、EML纯文本及PDF/XLSX/TXT附件。提取真实上传内容，逐字段保存文件SHA、页码/单元格/文本行、原文、方法和时间。不是调用模型或联网，不拿模拟数据冒充成功。

建议单独保存不可变supplier_extraction_runs，不能直接进入报价。浏览器选择一条建议填表，对照原文补齐缺项，保存待复核报价，再人工确认后才可参与核算。原始提取值、人工改值和来源同时保留，不能绑定别的源文件。缺少币种/单位/价格/交期等不猜测；公式不执行，扫描无文字层明确转人工。原手工入口保留。

限制：不保证任意排版PDF或OCR；单位/币种/日期未识别时需补充；没有模型准确概率。XLSX解压50MB、20表、1000行、100列、100条建议及PDF30页限制。解析不占用模型额度，单独限流。

## 本地真实浏览器与文件验收

真实Chrome Headless Shell桌面1440×1000，通过真实HTTPS访问本地Uvicorn，未mock HTTP；两个独立浏览器上下文实际登录管理员/reviewer。服务器及浏览器放在同一执行会话，退出后结束测试服务，不涉及公网。

最终20步通过，111条浏览器页面接口响应均200；另通过真实HTTP验证reviewer访问运行指标403（在steps与server.log记录）。内容包括RFQ预览上传、来源复核、3页PDF自动提取3家报价、逐条人工确认、三方案、不同角色审核审批、真实PDF/XLSX下载、V1数量100→V2数量500及关联报价影响。已审批100件快照不被覆盖。

下载文件重新用PyMuPDF/openpyxl打开，件号与合计1378.00匹配，SHA256与浏览器记录一致；PDF实际渲染查看，中英文字和金额无截断。见browser/download-readback.json。

保存5张成功截图、2张失败时截图、原始HTTP状态/耗时、下载文件、server.log及result.json。文件夹evidence/independent/browser，均为合成内容，不含会话Cookie或真实密钥。

失败记录保留：

- 系统Chrome初次启动因环境不支持AF_UNIX单实例socket而失败；改用Chrome Headless Shell后实际运行成功。不是应用通过。
- 第一次完整浏览器流程在保存V2后立即填写对比表单，页面重绘使脚本输入丢失并等待超时。等待新版本实际显示后重跑通过；未篡改失败记录。
- 扩大全量测试时6个fixture登录返回429：新旧测试共用固定测试IP触发真实限流。改为每个用例独立测试客户端IP，未放松生产限流。原始249 passed/6 errors日志保留。

## 最终自动化结果

- 全量pytest：255 passed，1条Starlette/httpx第三方弃用警告，32.66秒。原始输出final-pytest.txt。
- 新专项9项：四种供应商原件格式真实提取→改值→确认→报价、扫描及公式拒绝、旧生产接口绕过拒绝、分项舍入与尾差、多明细运费一次计入及Excel总额、真实v0.7 Schema升级三次重开。
- 兼容fixture由归档v0.7原store/reviews代码实际生成，明确合成客户/官方模拟成本，升级后原件字节、已审批49.89金额及原report_json均不变，外键和审计校验通过；不是对现网库的验证。
- 四个DOM套件11+6+6+8=31断言通过。没有把DOM结果代替上述真实浏览器流程。

## 复现与下一步

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-tested.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/prepare_desktop_acceptance.py
# 本地安装playwright和可用Chrome Headless Shell；不需要业务平台Key
QUOTEPILOT_TEST_PYTHON=.venv/bin/python CHROMIUM_EXECUTABLE=/absolute/path/to/chrome-headless-shell node scripts/independent_browser.cjs
.venv/bin/python scripts/verify_browser_downloads.py
```

脚本使用测试专用密码、临时SQLite和自签名本地TLS；仅监听127.0.0.1，不接受生产库或生产Key。API不自动部署。

本地本轮验收通过，待后续集中做真实Genesis/MOI调用、隔离预览部署及录屏。平台搜索历史provider_unavailable、本轮无外部调用；公网、原生能力、完整多租户与生产容量仍未验收。
