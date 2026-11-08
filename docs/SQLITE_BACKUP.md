# SQLite 备份与恢复

本功能适用于部署本次代码之后的实例。它不能取得旧实例中尚未导出的数据。

## 管理员下载

管理员登录后访问 `/api/admin/backup/download`。已有生产管理员中间件保护此接口；匿名请求返回 401。
接口使用 SQLite 在线 backup API 生成一致性快照，包括已提交 WAL 数据，以及 source_files 表中保存的原始文件 BLOB。
快照通过 `PRAGMA quick_check` 后下载，响应头 `X-Backup-SHA256` 用于校验。临时服务端副本在响应结束后删除。
接口不接受文件路径，不导出环境变量，不提供网页上传恢复功能；当前单团队管理员有权访问全部业务数据，备份应按同等权限保存。
源码仍使用临时 SQLite，备份下载并不等于自动持久化。

## 离线恢复验证

停止目标服务的写入，安全传送备份到目标运行环境，先验证 SHA256，再恢复到**新的数据库路径**：

```bash
PYTHONPATH=. python scripts/restore_sqlite.py backup.sqlite3 restored.sqlite3 --sha256 ACTUAL_DOWNLOADED_HASH
```

命令拒绝覆盖任何现存文件，检查完整性和外键错误；不会自动修改 `QUOTEPILOT_DB`、重启服务、迁移数据库或灌入示例素材。
核对恢复后的表行数及原始文件后，部署人员再配置新的 `QUOTEPILOT_DB` 路径。
Render Free 不提供持久磁盘/Shell/SSH/one-off jobs，且重新部署、重启和休眠会丢失临时文件。
因此上述恢复流程不能假定在 Render Free 上有 Shell 可用；需要在有权访问文件系统的运行环境执行。

## 当前现网的阻塞

旧版没有整库导出接口。现有 Render 连接只支持部署、状态、日志等操作，不能下载旧实例 SQLite。
浏览器的 Render 登录已失效，GitHub 登录尝试得到“该账号只连接部署、未绑定登录方式”的提示。
即使重新登录，Free 套餐也不会因此获得 Shell。当前未导出现网全量快照、未声称完成恢复校验。
只有取得可核验的旧备份，或用户明确确认现网新增数据可放弃后，才能继续此次部署。

验证依据：2026-11-08 实际读取 https://render.com/docs/free.md 和当前服务配置（plan=free）。
