# 固定版本实机容量补丁记录（2026-10-03）

在固定 `Build 25480438` 上将容量插件临时复制到官方 `bin/plugins`，通过 marker 启用后从 Steam 正常启动游戏。日志记录：

- `loaded`：官方 loader 实际加载插件。
- `applied`：25 个版本指纹位置全部通过并写入，`patched=25`。
- 插件源码包含卸载回滚；本次记录在强制停止进程前未收到 `unloaded`，因此只把回滚作为代码路径，不把它算作本次实机收据。

机器记录：[live_capacity_patch_runtime_20261003.jsonl](live_capacity_patch_runtime_20261003.jsonl)，验证收据：[live_capacity_patch_runtime_verification_20261003.json](live_capacity_patch_runtime_verification_20261003.json)。

本次还通过 `NetworkCApi.game_session` 与 `GameSessionCApi.num_peers` 做了两次只读观察，session 从空变为有效对象，但两次 `peer_count` 都是 `0`。这次实机结果只证明容量常数补丁能在该 build 的官方插件入口执行并保持到卸载；没有加入第五账号，没有调用 Party/PlayFab 或 GameSession 写入 API，也没有证明 confirmed-peer、Player Clone、客户端同步或完整任务流程。验证后已停止游戏并移除自制 DLL 和 marker。
