# Render上线操作与费用确认

## 已核实的适配结论

Render支持Docker及FastAPI、托管HTTPS和onrender.com域名。当前Python项目可直接采用Docker Web Service；无需为了上线重写成Workers或迁移数据库。已修复运行端口读取PORT，以及从RENDER_EXTERNAL_URL取得实际公共Origin；密钥使用服务端运行时环境变量或secret文件。

免费实例的本地文件系统在重启/重新部署/休眠时丢失，不能附加持久盘，因此不满足本项目原邮件、SQLite和审计记录持久化验收。当前最小变更路径是单个付费Web Service加1GB持久盘，延续SQLite。它是共享团队演示，不具备多租户隔离，不应接收真实客户敏感数据。

## 费用边界：待账户所有者确认，尚未创建

`deploy/render.paid.yaml`是待审阅的付费模板，不是已申请的服务。使用官方当前Blueprint规格ID`0.5c-512mb`、Singapore、1GB盘、自动部署关闭。官方文章给出的旧称Starter参考计算费为7美元/月，持久盘为0.25美元/GB/月；参考合计约7.25美元/月，**不是账户实时结算报价**。工作区套餐、网络、构建超额、税费和模型调用不包含在这项参考中。实际创建前必须读取账号控制台价格并取得明确确认；不升级工作区套餐，不增加持续计费资源。

如果该账号有已付费可复用服务/额度，应先核对现有资源，避免另建重复服务。若预算要求完全免费，需要调整持久化架构并验证，不把临时文件系统包装成稳定部署。

## 授权后执行顺序

1. GitHub连接后，读取账号身份，选用其拥有的私有仓库；源码已在本地Git保存v0.7.0基线与本轮提交。设置真实remote后推送并记录完整SHA及仓库URL。
2. 手动运行`.github/workflows/container-acceptance.yml`。它实际docker build并启动容器，验证PORT、会话、上传和容器重建后的数据持久化，不调用模型。无Docker成功日志前不声称镜像可用。
3. Render连接后读取账户和已有服务；校验模板及实际资源价格，向所有者请求付费创建确认。未经确认不提交模板。
4. 配置服务端GENESIS_ACCESS_TOKEN、至少12字符的演示密码、随机会话密钥、MOI_WORKSPACE_ID。不要把值提交到Git、前端或日志。使用Render生成的公共域名，无需先购域名；首次构建/启动以真实日志修复。
5. 检查挂载路径`/data`对镜像UID10001可写。当前未执行真实Render挂载测试；若出现权限错误，先根据平台实际挂载权限修复，不用临时目录掩盖丢数据风险。
6. 取得部署成功的实际URL后，从独立外部浏览器完成正常与异常流程；运行`scripts/accept_deployment.py --url https://ACTUAL_HOST`取得真实Genesis、Excel和云端回执。此脚本不是浏览器替代品，两个结果分别保留。
7. 重新部署/重启服务后重新登录核对之前导入文件与报价。确认数据仍在持久盘，导出的历史快照金额不改变。

## 当前状态

GitHub/Render连接等待授权；未设置remote、未推送，GitHub commit未知。真实Docker构建未执行：没有CLI/daemon，且rootless命名空间被拒绝。Render服务未创建，公网URL不存在。已完成本地真实进程的Render风格环境启动、上传限制、错误处理、会话与SQLite重启留存检查，不等于Docker或公网验收。

官方依据（2026-11-06读取）：
- https://render.com/docs/docker
- https://render.com/docs/web-services
- https://render.com/docs/free
- https://render.com/docs/disks
- https://render.com/docs/environment-variables
- https://render.com/docs/blueprint-spec
- https://render.com/articles/best-netlify-alternatives-in-2026
