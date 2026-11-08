# P1 独立免费预览 · 2026-11-08

状态：**未完成公网部署/验收，未产生可访问的演示URL。** 正式Render服务与SQLite未修改，未创建任何付费或免费新Render资源，没有要求网页登录。

## Render只读核查

现有连接成功读取My Workspace，tea-dbmpl3lg1s2s73bin610。仅有正式服务quotepilot-demo/srv-dbni3bk9v7es73cr4rd0，计算plan=free，buildPlan=starter，branch=release-v0.7，autoDeploy=no。未触发部署、重启、环境变量更新或正式站点应用请求。

当前官方Free文档确认，Free计算服务仍消耗工作区流水线分钟和流量；绑定支付方式时超额可能计费。现有连接没有额度、支付方式或消费上限的读取/限制能力，不能把plan=free等同零账单风险。因此没有贸然创建服务。https://render.com/docs/free

## 零账户临时预览尝试

使用官方Cloudflare Quick Tunnel方案，单独随机管理员/reviewer密码与会话密钥、全新合成SQLite、禁止公众注册，剔除所有Genesis/MOI/Render Key，不指向正式数据库。原件与预览数据仅在隔离临时目录。隧道仅映射测试进程的127.0.0.1:8877，不映射其他应用。

实际cloudflared 2026.10.7请求创建临时隧道时，DNS/出站网络失败：lookup api.trycloudflare.com / network is unreachable。未分配trycloudflare随机域名，未进行公网业务E2E。

第一版URL提取器误把错误消息中的api.trycloudflare.com当作预览URL，健康检查403；该结果从未记为成功。现已修复并增加3项契约测试，重试一次后正确报告无域名。原始失败记录保留于attempt-1-url-parser.json、attempt-1-tunnel.log；最终result.json无URL且public_acceptance=false。未无限重试。

Quick Tunnel本身是进程存活期间的临时预览，不是持久托管；即使连通，也必须记录关闭时间，不能当成长期部署地址。官方参考：https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/

## 已完成适配与回归

- acceptance_server支持测试专用公网Origin、随机凭据与仅本机HTTP上游；设置公网Origin却没有随机凭据时拒绝启动。仍强制production访问控制、mock业务模式、不播种赛事样例、不加载平台密钥。数据库路径始终是独立测试文件。
- 浏览器验收脚本支持指定目标URL和已有测试服务，凭据只从临时环境读取；结果记录HTTP状态、耗时、角色及截图，不记录请求密码或Cookie。
- 本地真实Chrome+HTTPS复跑20步、111条页面接口响应，全部成功；不是公网结果。见local-browser/result.json及server.log。
- 预览URL识别+生产权限+商业报价专项：20 passed，1条第三方弃用警告，见tests.txt。
- 既有已验收业务代码未重新开发，改动仅为测试/预览基础设施。

## 下一步

具备可核验的免费额度/零消费上限后，可创建与正式站点完全独立的Free预览；或者在允许Quick Tunnel出站DNS及连接的环境中运行scripts/quick_preview.py，再执行真实公网验收。当前无需用户额外登录，先继续P2本地实录。
