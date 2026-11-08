# P3：公开参赛材料与提交门禁（2026-11-08）

官方要求已通过 https://matrixorigin.cn/matrixnext 当前活动页核对：可运行智能体、演示视频、说明文档三个评委可访问链接；视频≤3分钟；文档包含问题、方案、技术栈、创新点与使用说明，命题赛道另需数据合规声明；需要密码则注明。活动页要求11月11日前提交，没有在本次核验中确认精确时分，因此不擅自假定23:59。

## 实际可访问链接

| 项目 | URL | 验证 |
|---|---|---|
| 说明文档 | https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/ | 外部浏览器可读，无Cookie/Authorization HTTP200 |
| 视频v2 | https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/video/ | 外部浏览器完整播放175.083秒，无跳播、未静音、ended=true |
| MP4原文件 | https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/quotepilot-v2.mp4 | 无登录完整下载HTTP200，9434302字节，与本地SHA256一致 |
| 可运行智能体 | **缺失** | 没有独立公网业务环境，禁止使用材料站/localhost/旧正式站冒充 |

当前三项提交链接完成2/3，**不满足完整提交条件**。未进行报名或提交，不存在提交成功回执。

## 托管与证据

新建完全独立公开材料站，project_id=appgprj_6af04efb54488191b5606bff81038890；公开访问策略已生效，不要求评委登录。它只提供合成业务的视频与说明，不提供写入正式数据或模型密钥的接口。没有修改原Render服务、正式分支和SQLite。

最终发布源提交4d05fcaf01627a7aeef69e1ed3dad39fa9185889，发布成功回执见evidence/final-p3/publication.json。公开网页源副本位于portal-source/；MP4不进入Git，公开站/用户副本另行保留。

最终匿名HTTP三项请求实际状态、响应耗时、类型、字节及哈希见public-http-final.json。一次未显式设置User-Agent的普通urllib请求403，原因未确认，失败保留；使用与首轮一致的验收客户端后，三项均200。没有将403称为网站永久故障或绕过任何验证码。

正式完整视频播放证据位于evidence/final-p2/playback-review.json；完整解码、字幕、配音与技术验证分开记录，不把抽帧称作全片播放或把机器音轨校验称作人耳认证。

## 最后仍需完成

1. 取得可核验零额外计费的独立Python托管入口，或确认现有Render工作区免费余额/支付/消费上限；不能在未知收费风险下直接创建。
2. 仅部署合成数据，独立管理员/复核员凭据，禁止公众注册，与正式数据库隔离。
3. 从外部浏览器完成上传→真实Genesis建议与人工确认→供应商原件核验→核价→数量版本变更→双角色审批→PDF/Excel及MatrixOne回执；保留HTTP状态/耗时/失败。
4. 公网通过后再向公开说明文档添加智能体URL、两角色演示账号和休眠/重置限制。当前不发布正式账号或虚构测试账号可用。
5. 三链接全部验证后，才可由原报名账号填写官方提交入口并保留真实回执。当前无需额外登录，MOI原生工作流列技术待办。
