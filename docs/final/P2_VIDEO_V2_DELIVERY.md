# P2：产品视频v2

采用真实产品操作录屏作为全屏主画面，统一深绿顶栏、暖白字幕与数量强调；去掉v1的左文右图、静态截图平移结构。先输出18秒开场样片与完整175秒分镜，再制作正式版。

## 内容

开场“100→500，原报价还能发吗”；自然语言来件经真实Genesis提取、来源与人工确认；供应商原件规则解析及核验；透明成本；客户数量更新、关联报价影响；500件重新核价与双角色审批；PDF/Excel导出；页面操作触发的真实MatrixOne应用层镜像回执。全部业务价格为合成数据，所有操作来自独立本地服务。

视频使用zh-CN-XiaoxiaoNeural中文合成配音。语音库默认certifi证书不包含执行环境CA，首次失败记录保留；仅改为系统/环境信任根后成功，未关闭TLS校验，未使用新的API Key或付费配音服务。音轨不再只有字幕和低音量合成音。

## 制作与验证

- 18秒样片在实际浏览器从0播放到18.048秒ended=true。
- 正式版1920×1080、24fps、约175秒，H.264/AAC。精确时长、字节及SHA以evidence/final-p2/video-validation.json为准。
- 背景全部为真实WebM操作录屏，字幕和标题仅为编辑标注，没有用生成产品界面或静态截图冒充操作。部分操作按叙事进行剪辑及变速。
- 完整文件实际解码无错误，音轨平均-20.6dB、峰值-2.8dB（若最终重导出，以technical-validation.json为准）。不能把音轨/音量检查当作主观人耳听感结论。
- 公开页完整播放检查单独保存在playback-review.json，不仅靠抽帧；看到叙事错位时调整镜头再导出复核。主观配音质感没有冒充真人试听认证。

## 限制

画面标注“真实本地操作·合成案例”。当前公开链接是视频/文档材料站，不是业务公网服务。MOI原生工作流、原生Snapshot/Branch、多租户等未验证内容只在技术文档列待办，视频不声称成功。真实Genesis和MatrixOne均有应用操作路径和回执，仍不代表AI自动完成供应商核验或绕过人工审批。

最终修正版已在外部浏览器连续播放至175.083秒ended=true，未跳播、未静音，无视频错误；期间核对模型输入、版本影响、重审批与结束画面。公开MP4匿名下载SHA256=d710aa5de4e3704b0298cfa2707469264479ec6ff253cb7558a80cfb24afb29b，与本地9434302字节一致。首轮全片播放发现并修正AI镜头错位，前后证据均保留。

公开评委视频页：https://quotepilot-matrixnext-2026.bracedcake5.chatgpt.site/video/ 。旁白、时间线、生成脚本、失败日志与验证记录均可核查。

## 已保存交付物

- [18秒开场样片](https://chatgpt.com/library?file_id=libfile_8dcf443e9904819188b1464e48ac2e14&account_id=personal)
- [175秒正式成片](https://chatgpt.com/library?file_id=libfile_06540098343c8191abe1d62356da44f7&account_id=personal)
- [36项原始素材、配音、字幕与回执](https://chatgpt.com/library?file_id=libfile_3af60767c6e0819180b625b372c5bb83&account_id=personal)

以上为用户保留副本；评委使用公开视频页，无需ChatGPT个人文件权限。素材ZIP为20456276字节，SHA256=a165800f67030de4041e09ce23473a5480cd07d6d748968354bca439af34268e。
