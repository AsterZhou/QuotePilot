# P2 三分钟产品视频交付 · 2026-11-08

已验收业务基线43e76e0保持，未新增业务流程。P0真实平台适配和P1隔离预览验证分别在6921ec5、54b8701提交；本阶段只增加可复现媒体制作、浏览器录像和证据。

## 运行与验证

- 最终全量自动化回归：269 passed，1条第三方弃用警告，32.63秒；见evidence/sprint-p2/final-regression.txt。
- 真实本地桌面浏览器：20步、111条页面API响应全部成功。管理员与复核员两个实际会话，完成上传、原件提取、人工确认、报价核算、双角色审批、版本影响与导出；见browser/result.json的实际HTTP状态、耗时、步骤和截图路径。未拦截或伪造HTTP接口。
- 实际导出PDF/Excel均读回核对，合成示例总额1378.00元；录像和截图随素材包提供。
- 视频10段恰好180秒，1920×1080，24fps，H.264/AAC。最终字节数与SHA256以video-validation.json为准。
- 完整MP4解码退出码0；每段抽取一个实际视频帧检查非黑画面，并检查音轨电平，见frame-decode.json。实际查看10段联系表以及平台/成本放大帧，中文字形和字幕可读。

## 交付范围

字幕版成片包含真实短录屏、实际界面截图平移、真实导出PDF和真实平台回执卡。不是连续180秒无剪辑屏录。所有报价均为合成案例，画面标明本地运行；宣传价值为待客户验证的价值主张，不编造商业ROI或准确率。

交付MP4、原始管理员/复核员WebM、五张页面截图、导出PDF/Excel、旁白文本、SRT/ASS字幕、执行镜头表及媒体校验记录。源码和回执保存在Git，视频与原始素材另行保存。

## 失败及修复记录

1. Playwright首次录像缺FFmpeg依赖，保留attempt-recording-dependency.json；补齐后真实重录成功。
2. 首次媒体滤镜问题，保留attempt-render-filter.log；修复后完整导出。
3. 首版ASS字体缺中文，保留attempt-subtitle-font.json；改用静态中字重中文字体并指定唯一family，重新渲染、解码和目视检查，未交付缺字版本。金额换行进一步缩短，保证完整数字可读。
4. 免Key Edge TTS尝试因证书链校验失败，见voice-attempt.json。没有关闭TLS校验或使用付费配音；当前为中文字幕及自制低音量氛围音，无旁白声轨。旁白稿可供后续录音。

## 尚未完成与部署待办

- MOI原生启动HTTP400，无执行ID；工作流disabled、实例列表为空。Genesis独立调用和MatrixOne应用层镜像成功，不等于完整原生工作流运行。
- 独立公网环境未部署成功，无测试URL；Render现有API无法核验免费额度/支付上限，Quick Tunnel出站DNS失败。没有接触正式站点或现网SQLite。
- 本地业务闭环和成片已可演示；仍需可核验零成本托管条件后执行公网验收，以及平台可用条件下补原生执行终态证据。当前不要求额外登录，不创建计费资源。

## 已保存交付物

- [180秒字幕版成片](https://chatgpt.com/library?file_id=libfile_063e84adfe28819182a97d5419207f5f&account_id=personal)
- [原始录屏与演示素材](https://chatgpt.com/library?file_id=libfile_7406f2e0daa881919f4852c5cc5563ce&account_id=personal)
- 成片SHA256：63c6490934273668118ad7191c44a3677eb49a949497702ccdf509bb8e6ce653，5811482字节。
- 素材ZIP：21个文件，5985483字节，SHA256：4657d4bbc8528df2673baa794766d7867b990e05ba2600b19c49da02c1cb9d53。
