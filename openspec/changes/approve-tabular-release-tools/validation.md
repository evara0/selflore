## 本地准备

- 复用归档能力补丁，改动私有工具client.py、protocol.py、runtime.py、tests/test_executor.py。保留原字节；原补丁因Windows换行无法直接git apply，逐hunk严格匹配一次后应用并保持原文件换行，未改公开历史补丁。
- 执行器模拟36项通过。实际runtime.readiness函数抽取验证：schema未就绪拒绝、就绪接受、错误数据库身份／Origin拒绝；固定bundle可解析，篡改摘要拒绝。
- 只读服务器核对旧批准配置与所有工具原摘要相符。一次性升级资料放在Git忽略的local-deployment/admin-upgrades/20261022-tags-table-tools；以先前实际验收过的upgrade.py模式固定新旧配置、四个工具、entry和broker摘要，保留恢复能力，不执行root代码或新增sudo。
- 初版升级资料已上传到部署账号同名私有目录且三份文件远端hash一致；最终候选和root命令在全部检查通过后固定，最终摘要以该私有目录preparation.json／upload.json为准，旧版材料不供执行。
- 新能力工具的候选20261022144433-269374b2完成后端204、前端79、备份适配器3、执行器36、lint／构建；浏览器34/35通过，另一个旧随机阅读测试竞态已单独修正，不能将该候选标为通过。
- root安装、停写、生产备份、迁移及激活均尚未执行。视觉审查不适用：本变更只调整私有工具和操作记录，没有展示代码改动。
