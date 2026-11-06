# 可直接发给 MOI 技术支持的问题说明（未发送）

主题：MatrixNEXT RFQ项目工作流已保存但disabled、无运行ID；当前工作流/计算资源接口503

您好，我们在MatrixNEXT 2026开发QuotePilot RFQ报价应用。Genesis独立Responses API与MOI SQL报价快照读写已有真实成功记录，但原生工作流尚不能运行，希望协助核对工作区的运行资源和启用条件。

## 定位信息

- 工作区ID：ec94c942-2d64-c6be-c968-e793caaef007。
- 工作流ID：45e246b6-9a6f-5331-82cd-44c00f67cb18。
- 使用官方Product API：https://api.moi.matrixorigin.cn/v5；个人令牌通过X-API-Key、工作区通过X-Workspace-ID提供。此说明不包含令牌。
- DSL使用当前工作区真实WorkItem目录中的moi:data.sql.process v1与moi:llm.output.generate v3：读合成RFQ→模型建议→待复核建议回写→读回。

## 2026-11-05已发生的结果（历史记录）

- POST /workflow/v2/workflow-deployments返回HTTP200/code=OK，生成上述ID。
- 创建返回status=disabled，deployment.version=0，workflow_def_id及workflow_version_id为空。
- GET详情status=disabled，available_actions=[update,delete,enable,list_executions]。
- compute_resource_bindings在当时返回中缺省，不能把它当作已配置或已核验的空数组。
- POST .../executions返回HTTP400，完整业务体为`{"code":"ErrParamInvalid","msg":"Bad Request"}`，没有execution_id。
- POST .../resume亦返回HTTP400与同一错误体；随后读取执行列表为0。没有连续重试或新建重复工作流。
- GET /compute-resources当时为HTTP200/code=OK/data=[]。

## 2026-11-06本轮只读诊断

以下每个接口仅调用一次，没有启动、恢复或创建操作：

| GET路径 | HTTP | 返回 |
|---|---:|---|
| /workflow/v2/workflow-apps/{workflow_id} | 503 | 非JSON：upstream connect error or disconnect/reset before headers. reset reason: connection timeout |
| /workflow/v2/workflow-apps/{workflow_id}/executions | 503 | 同上 |
| /compute-resources | 503 | 同上 |
| /compute-resource-specs | 503 | 同上 |
| /compute-resources/worker-images | 503 | 同上 |
| /compute-resource-specs/management-permission | 200 | code=OK，data.can_manage_specs=false |

当前503没有平台业务错误码，不能据此推断身份无权创建计算实例。can_manage_specs=false仅证明不能管理“规格”，不等于不能基于已有规格创建实例。当前创建权限、可选规格、Worker镜像和价格均无法验证。

## 希望协助确认

1. 上述disabled/version0/空定义版本是否表示定义只保存未激活？在available_actions包含enable时，应使用哪个正式公开接口或UI操作完成启用？resume针对paused资源是否不适用于此状态？
2. 工作区是否已分配可用task/query计算资源、可选规格与Go/Python Worker镜像？参赛账号是否需要单独开通任务执行权限或资源额度？
3. 此次400能否提供更具体字段校验或依赖错误？请求无execution_id，怎样取得服务端追踪信息？
4. 503是工作区资源服务、网络入口还是平台端依赖异常？我们能够读到规格管理权限，但其他资源与工作流读取超时。
5. 平台原生模型节点能否使用qwen3.8-flash，以及会使用哪一类已配置模型通道？目前节点未执行，不声称模型节点已通过。
6. 若须创建计费实例，请先给出规格、单价、计费方式、自动缩容与停止/删除规则。账户所有者尚未授权新增持续计费服务，暂不创建。

可提供的脱敏附件：evidence/launch_20261106/moi_readonly_audit.json（含UTC时间、HTTP状态、返回体及服务实际返回的追踪头）、v0.7 native_attempt.json/native_resume.json、integration/rfq_native.yaml。没有改写平台状态、伪造执行ID或用本地Mock代替原生运行。
