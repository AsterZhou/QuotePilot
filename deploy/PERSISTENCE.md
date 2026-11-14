# 决赛正式服务的存储与恢复

商业报价、上传原件、供应商目录、审批和审计写入 `QUOTEPILOT_DB` 指定的 SQLite。应用可将已审批报价同步到 MatrixOne，原生工作流另行写入其业务表。完整的工作库需要单独保护。以下命令使用原服务和已有的 MOI 工作区，分别保留不同时间点的备份。

## 切换前

为避免备份后出现新的成功写入，先安排短暂的停止写入窗口，排空请求和后台作业，再从现有管理员入口下载最终整库。保存 API 的 `X-Backup-SHA256` 和报价、导出记录、原件 SHA-256、审计链头。分别留存已知的旧库和当前库。选定当前工作库的快照并记录摘要，旧审计链可独立读取。核对迁移前后的报价编号和审计事件，防止将不同业务历史相互覆盖。

## 在全新路径恢复

在原服务实际挂载的持久卷上准备新的文件路径和同一卷内的备份暂存路径。进程须有写目录权限。在部署镜像或仓库根目录下运行以下命令，替换示例中的路径及摘要。离线安装只接受独立 SQLite 备份，原子发布前会检查 SHA-256、结构、外键、原件和审计链。文件已存在、有 SQLite 辅助文件或校验失败都会中止。

```sh
python -m quotepilot.persistent /staging/final.sqlite3 /data/quotepilot-live.db --sha256 "$BACKUP_SHA256"
```

在原服务配置 `QUOTEPILOT_DB=/data/quotepilot-live.db` 和 `QUOTEPILOT_PERSISTENT_MOUNT=/data`，两处路径需与实际挂载相符。持久化模式先核对 Linux 挂载、实际路径和既有业务库，再启动业务服务。缺失数据库、挂错卷、只读卷、空文件或证据损坏时，进程启动失败，演示种子不会补成新库。对从未启用持久化的免费演示实例，既有演示入口仍可使用。

Render 添加磁盘可能立即触发部署。先安排好数据冻结、最终备份及可恢复到同一服务的运维入口。启动后核对上述业务编号、原件、外键、审批与导出。关闭并重新启动应用，再次核对相同记录。保存实际结果后才能将服务的临时存储标志改为与实际部署一致的值。代码回滚应使用同一份已验证的持久化工作库；恢复旧时间点会丢失该时间点之后的写入，需为后续写入另外保全。

## 将整库归档到既有 MOI 卷

此命令使用服务端既有 `MOI_WORKSPACE_ID` 和 `MOI_API_KEY` 或原有 Genesis 凭据，目标为用户已指定且可写的文件卷。对管理员下载的备份运行：

```sh
python -m quotepilot.moi_backup archive /staging/final.sqlite3 --sha256 "$BACKUP_SHA256" --volume-id "$MOI_VOLUME_ID"
```

工具上传完整备份，将文件关联到指定卷，再实际下载并流式核对原文件长度和 SHA-256。成功输出含卷 ID、文件 ID、摘要、字节数的 JSON，请与快照日期一并保存。一次归档对应一个新文件，不改动报价同步表或原生工作流。远端中途失败可能留下已上传文件，工具不会据此返回成功回执。上传的归档只代表该时间点，之后产生的新业务仍需由工作库持续保存；该命令由运维显式执行。

```sh
python -m quotepilot.moi_backup restore "$MOI_FILE_ID" /staging/readback.sqlite3 --sha256 "$BACKUP_SHA256"
```

恢复到新位置后，以独立副本核对业务记录。原服务的跨重启验证和 MOI 工作区的真实归档回执需要分别保存。

[Render 持久化文档](https://render.com/docs/disks) · [MOI 上传](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/resource-center/catalog/upload-file.html) · [关联文件到卷](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/resource-center/catalog/create-file.html) · [下载](https://docs.matrixorigin.cn/moi/zh/5.0/reference/api/ai-studio/resource-center/catalog/download-file.html)
