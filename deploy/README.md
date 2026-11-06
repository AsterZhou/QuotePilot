# 独立公网部署（v0.7）

当前没有部署服务器/容器托管账户，也没有公网URL。此目录交付真实Python应用的部署配置，不是已经在线的服务。Sites的Workers运行环境不能直接运行现有FastAPI/PyMuPDF/SQLite后端，因此没有发布脱离后端的静态演示页。

## 部署条件

Linux服务器、Docker Engine和Compose v2；可解析到服务器的域名；开放80/443；允许出站HTTPS访问Genesis与MOI。需要能持久保存Docker卷。当前环境没有Docker，因此镜像构建、Compose启动、Caddy签证书未执行，首次在目标主机运行仍需排查环境兼容性。

1. 将源码放到服务器，进入QuotePilot目录。
2. 在源码目录外初始化密钥（此脚本只在目标服务器运行；请使用sudo使挂载文件归属容器UID 10001）：

```bash
sudo QP_SECRET_DIR=/var/lib/quotepilot-secrets python3 deploy/init_secrets.py
```

按隐藏提示输入Genesis个人令牌及至少12字符的演示访问密码。脚本生成会话密钥，不覆盖已有密钥。不要提交此目录，不要把令牌放在前端或构建参数中。Docker build只复制指定源码和官方模拟素材，不复制工作数据库或运行记录。

3. 设置不含密钥的部署参数：

```bash
export QUOTEPILOT_DOMAIN=your-actual-domain.example
export MOI_WORKSPACE_ID=your-workspace-id
export QP_SECRET_DIR=/var/lib/quotepilot-secrets
bash deploy/deploy.sh
```

必须把示例域名和工作区替换为实际值。Caddy自动申请HTTPS证书，应用端口不直接暴露公网。SQLite及原文件BLOB存在`quote_data`持久化卷。前后端同域部署，不需要浏览器拿到Genesis凭据。不要执行`docker compose down -v`，它会删除持久化卷。

4. 打开实际域名，输入演示访问密码。当前是单团队共享演示库，不具备多租户隔离、企业SSO或角色分权；请只使用赛事素材或合成数据。业务字段里的复核人是人工填写的审计字段，不是已认证的企业身份。
5. 从另一台机器实际执行：

```bash
python scripts/accept_deployment.py --url https://YOUR_ACTUAL_DOMAIN
```

该命令需要安装项目依赖，在隐藏提示输入演示访问密码；直接调用服务器中的真实Genesis并写入合成测试数据，使用明确标记的测试审批人。正常与缺价拦截、人工数量变更留痕、Excel下载、云端快照均须通过，报告保存到`evidence/deployment_acceptance`。它是外部HTTP验收，不等同浏览器UI验收；浏览器仍须实际操作上传、提取、复核、核价、审批、下载并记录结果。

## 实际已执行的部署相关验证

- 生产配置缺失时拒绝启动、未登录API拒绝、Secure/HttpOnly/SameSite会话、Origin校验、登录限额的测试已执行。
- `bash -n deploy/deploy.sh`、Python编译检查、Compose YAML结构读取已执行。
- 同代码在临时库的本地HTTPS环境中，真实Genesis与MOI快照完整HTTP验收通过。测试CA仅用于本地验证，不是生产证书。
- Docker构建/运行、公网TLS、另一设备的浏览器闭环：未执行。不可把上述本地测试改写成公网部署通过。

## 运维边界

单个应用worker共享演示库；按进程限制每小时30次模型提取，重启会重置计数，不能替代持久计费预算控制。登录错误按IP限额；会话8小时到期。会话密钥轮换会使旧登录失效。请用SQLite在线备份保存数据库；备份包含用户上传原文件和审计，不应公开。生产文件下载和API均要求登录；`/healthz`只返回最小就绪信息。
