# 固定版本实机容量补丁记录（2026-10-03）

在固定 `Build 25480438` 上将容量插件临时复制到官方 `bin/plugins`，通过 marker 启用后从 Steam 正常启动游戏。日志记录：

- `loaded`：官方 loader 实际加载插件。
- `applied`：35 个版本指纹位置全部通过并写入，`patched=35`。
- 插件源码包含卸载回滚；本次记录在强制停止进程前未收到 `unloaded`，因此只把回滚作为代码路径，不把它算作本次实机收据。

机器记录：[live_capacity_patch_runtime_20261003.jsonl](live_capacity_patch_runtime_20261003.jsonl)，验证收据：[live_capacity_patch_runtime_verification_20261003.json](live_capacity_patch_runtime_verification_20261003.json)。

收据中的旧版本 `peer_count` 字段现已标为 superseded：固定 build 的 live GameSession wrapper 与公开 SDK 的表布局不一致，旧探针把未闭合的 wrapper 偏移当成 `num_peers`，因此不能把那些数值当作可靠的只读 peer 观测。旧原始日志仍保留用于审计，但不再支持 `peer_count` 结论。修正后的 capacity plugin 只在已固定代码字节的 Network getter 上读取 session 指针，明确不读取 `peer()`、`num_peers()`、`in_session()` 或 `host()`。

修正后的合成快照测试为 `session_snapshot_synthetic_passed`，它只接受固定 EXE 身份、Network getter bytes、GameSession 底层 vtable bytes、bounded record count、稳定双读和最多八项记录；任一不匹配都拒绝。这样仍只证明容量常数补丁可以在该 build 的官方插件入口执行，不能证明第五账号、confirmed-peer、Player Clone、客户端同步或完整任务流程。验证后已停止游戏并移除自制 DLL 和 marker。
