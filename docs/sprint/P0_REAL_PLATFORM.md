# P0 真实平台集成 · 2026-11-08

基线43e76e0的426个文件已校验，Git树bb01844709a6dbaf0c3624eb8203c1ffaa134b6a；没有重新开发业务功能，没有操作Render正式站点或现网SQLite。使用原有用户提供的密钥，仅通过服务端进程环境注入；未创建新Key、计算实例或收费服务。

## 真实结果

- 五项预检均HTTP200：Genesis模型目录、原MOI工作流、实例、规格与规格管理权限。工作流disabled，实例data=[]；can_manage_specs=false只表示无法管理规格，不外推其他权限。规格中存在按credit/hour计价的task，未创建或启用。
- 原生工作流只提交一次：POST /workflow/v2/workflow-apps/45e246b6-9a6f-5331-82cd-44c00f67cb18/executions，HTTP400，code=ErrParamInvalid/msg=Bad Request。无execution_id，无运行成功；没有循环启动、自动enable或创建实例。disabled与无实例是当前观察，不把400详细根因说成已由平台确认。
- 独立Genesis Responses API真实成功：qwen3.8-flash，response_id=resp_d7c405e1-96fd-941c-9bb8-128862c49900；输入431、输出652、合计1083 Token，16.4秒。合成RFQ提取PN-0001、100 EA、FN，证据片段校验通过。没有把它称为原生工作流LLM节点。
- MOI异步SQL真实SELECT 1成功；通过已验收本地合成业务链生成双角色审批的商业报价，再写入独立quotepilot_sprint.commercial_quote_snapshots_v1并读回核对完整Base64和SHA256。
- 云端报价CQ-D886B700E98043F4 / v3；SHA256=c73d22522f83bf4eeabbb2ab5a69a5882bc2db446256e184957448d7ba2797e0。
- 四个真实SQL query_id：01a1b99d-1ed0-732a-babf-dd265cc3ff2b、01a1b99d-2484-7619-b128-bde321fa1bd5、01a1b99d-2e04-737d-a26d-911c37c0ceee、01a1b99d-311b-7bb8-8a35-67a165ddeec3。

这是应用编排的“本地审批→真实MatrixOne镜像”，以及独立的真实Genesis提取验证；不是MOI原生完整工作流成功，也没有自动将模型结果写为业务事实。没有真实成交价、真实客户、ROI或准确率声明。

## 适配与验证

新增platform_quotes.py：只接受已审批且两个不同账户的商业报价，写入隔离表，重复写入不覆盖原版本，读回冲突拒绝；主库存储仍为SQLite。native_workflow.py补充真实执行详情/结果接口与ID回执校验。business_cycle.py仅增加可选审批快照观察回调，原业务流程不变。

scripts/sprint_probe.py、sprint_live.py可复现受限调用；密钥仅从环境读取，不进入脚本/证据。live.json保存14次真实HTTP请求的状态、耗时、脱敏请求/响应、真实响应ID和用量；大快照记录摘要/大小，适配器核对完整内容。preflight.json记录资源状态。契约测试中的CONTRACT前缀ID明确不算平台证据。

 targeted regression: 见evidence/sprint-p0/tests.txt。模型费用未推算，已有Token回执不等于实际账单。

## 降级演示

可展示真实Genesis响应和MatrixOne哈希读回。原生工作流明确“尚未运行”，附400及disabled/无实例证据；平台技术亮点不包括未验证的Snapshot/Branch/Pick/Merge。平台资源/权限恢复后，只在已确认零新增付费资源的前提下提交专用合成RFQ原生执行并读取终态与结果。

当前官方文档核对：
- https://docs.matrixorigin.cn/moi/en/5.0/reference/api/ai-studio/data-processing/workflow-jobs/start-workflow-job.html
- https://docs.matrixorigin.cn/moi/en/5.0/reference/api/ai-studio/data-processing/workflow-jobs/get-workflow-job.html

官方说明：POST接收成功也不代表执行完成，必须保存execution_id并查终态；禁止runtime_context/run_once等未知字段。结果接口官方页本次检索不可读，适配保留端点，未声称已真实执行结果查询成功。
