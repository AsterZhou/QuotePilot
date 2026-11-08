# QuotePilot · MatrixNEXT 最终交付说明

问题：工业报价团队收到RFQ与供应商文件后，需要核对来源、计算成本、响应客户版本变更并走人工审批。QuotePilot围绕“客户数量100→500，哪些报价失效，如何重新核价与审批”形成可追溯闭环。

## 评委入口

- 业务智能体：**尚无已验收独立公网地址**。正式演示服务不作为新版交付入口，不提供其密码或改动其数据。
- 视频：https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/video/
- 说明文档：https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/docs/
- 两项已公开。ChatGPT个人文件链接、私有GitHub链接不能代替评委公开链接。
- 演示账号：独立业务环境未上线，暂不发布账号。上线后为单团队管理员和业务复核员两个独立账号，关闭公众注册，不提供真实客户数据。

## 架构与技术栈

浏览器原生JavaScript工作台调用FastAPI业务接口。生产访问中间件控制管理员与复核员、Origin、会话及限流；SQLite保存业务、原件和审核链。Genesis服务端适配器进行用户主动触发的建议提取，原文定位和人工确认后入库。Decimal确定性计算成本，审批后的不可变报价版本由PyMuPDF/openpyxl导出PDF/Excel。管理员可将已审批商业报价主动镜像至MatrixOne隔离表并读回完整内容与SHA256；SQLite继续作为主库。

核心栈：Python、FastAPI、Pydantic、SQLite、Decimal、PyMuPDF、openpyxl、原生HTML/CSS/JavaScript；模型通过Genesis Responses API，云端镜像通过MOI异步SQL API。视频由真实Chrome操作录屏和合成中文语音组成，不是生成的产品界面。

## 创新点与业务价值

- RFQ版本差异关联受影响报价，定位数量、规格等变化，保留旧审批，要求新版本重新核价审批。
- 字段级证据溯源、原始模型建议和人工修订分别保留，减少“这个数字从哪里来”的核查成本。
- 供应商原件规则提取→人工确认→参与成本；明示同规格/单位/币种约束，防止不具可比性的价格混用。
- 完整成本展开、整票运费分摊及分币舍入可复核，明确区分毛利率与加价率。

价值主张尚待真实客户验证，没有编造节省工时、商业ROI或模型准确率。

## 使用步骤

1. 管理员上传合成EML询价，规则解析；未可靠识别的自然语言问题，主动点击Genesis补充提取。
2. 查看模型输入、响应ID、Token及原文证据；人工填写/核对来源询价号、技术描述、件状、数量与单位，确认后才进入业务明细。
3. 上传合成供应商PDF/Excel/EML/TXT原件，规则提取候选字段，人工核验后确认。
4. 比较最低成本、最快交付、平衡方案；业务复核员审核，管理员独立批准；下载正式PDF/Excel。
5. 客户数量改为500件时登记新版本，对比差异及受影响报价；核对新需求后重新核价和审批。旧100件1378.00元报价保持；新成本5502.00元，单价按分舍入后总额6880.00元。
6. 管理员可主动同步已审批报价至MatrixOne，等待真实读回；超时状态未知时先查看保存回执，不能盲目声称写入失败或成功。

## 配置与复现

基线commercial-upgrades/5148740。依requirements.txt安装；使用独立SQLite路径，设置QUOTEPILOT_ENV=production、HTTPS公共Origin、独立管理员/复核员密码、32字符以上会话密钥。禁止使用正式SQLite进行验收。Genesis需要既有服务端环境变量GENESIS_API_KEY、GENESIS_MODEL_ID、GENESIS_API_STYLE，不能写入浏览器或仓库；未配置时明确Mock，不声称真实推理。MatrixOne另需MOI_WORKSPACE_ID，未启用仍可完成本地报价闭环。

本地隔离验收脚本见scripts/final_live_server.py（现有密钥通过隐藏stdin注入，数据库路径限制为tmp/final-live）；常规规则回归不需要真实Key。媒体制作依赖见media/requirements-video.txt和docs/final/P2_VIDEO_V2_SHOTLIST.md。

## 数据合规与访问限制

本轮公开材料、联调与视频仅包含自行构造的合成邮件、供应商报价和联系人example.invalid地址。未把真实客户原件、账号凭据或正式SQLite发布到材料站。演示价格不代表真实供应商报价、库存或成交价；AI输出不直接作为事实，不自动发送客户报价。既有赛事素材保持原项目状态，不因材料站公开而对外发布。

当前为单团队演示权限，不宣称完成企业SSO或多租户隔离。免费临时部署若使用Render，15分钟无请求会休眠，唤醒约一分钟，SQLite与上传文件可能在休眠、重启或重新部署后重置；因此不承诺数据持久保存，只接收合成演示文件并及时导出成果。

## 真实集成、验证及未完成项

真实Genesis已从页面操作进入询价提取/人工确认路径；商业报价页面操作已触发真实MatrixOne写入并完整读回。详见P1_REAL_USER_INTEGRATION.md，包含实际ID、Token、耗时、SHA及失败记录。MatrixOne为应用层镜像，不是原生Snapshot/Branch，也没有迁移主库。MOI原生工作流仍未运行成功，无执行ID，列为待办。

本轮全量自动化271项通过，1条第三方警告。真实浏览器重录11段业务操作无失败；后续5项复核覆盖已确认Genesis回执、云端保存回执、PDF/Excel、角色拒绝，71条资源/API响应成功。所有这些是本地验证，不是公网业务验收。

公网业务环境仍受可核验零成本托管入口阻塞。正式服务、正式分支和现网数据未修改；未创建计费资源。报名与作品提交状态未经回执核验，不能声明已成功提交。
