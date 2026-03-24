# TODO

## MVP
- [x] 确认 Chatbox 桌面端落盘结构
- [x] 起 FastAPI sync server 骨架
- [x] 起纯外挂 agent 骨架
- [x] 在真实 Chatbox 数据目录上做只读探测
- [x] 确认 Chatbox 官方 backup JSON 可恢复且结构可用
- [x] 验证 backup upload/download 基本链路
- [x] 新增 latest-meta / sync-backup
- [ ] 为 sync-backup 增加 force flags
- [ ] 优化本地/远端时间比较逻辑
- [ ] 增加下载文件命名策略
- [ ] 增加更清晰的导入提示

## 下一阶段
- [ ] Windows 更顺手的一键脚本
- [ ] 定时同步 daemon
- [ ] systemd user service
- [ ] Tailscale 接入说明
- [ ] 简单 Web 管理页
- [ ] blob / 附件同步评估
