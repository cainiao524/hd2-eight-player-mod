# 两客户端生命周期测试

当前交接状态见 [CURRENT.zh-TW.md](../github_handoff_20260927/CURRENT.zh-TW.md)。本页实际采样步骤须另行取得授权；2026-10-19 的整理上传不包含游戏访问。测试条件是两台电脑、每台一个客户端。飞船没有手动转移房主操作，房主退出后应如实记录自动转移或房间解散；既有房间解散观察不算通过迁移验收。

这个验收器只读取已经保存的 `hd2_live_session_snapshot_v1` 快照。它不会启动游戏、访问进程、调用游戏函数、写入内存或安装 Hook。加入和退出阶段还要求同一 PID 以及 `context`、`roster`、`game_state` 根指针保持一致，防止把不同房间拼成一条记录。

真实测试时，每个阶段可用一次性读取器保存一份不可覆盖的快照。把 `<PID>` 换成游戏进程号，把 `<DIR>` 换成空的证据目录：

```powershell
py -3.12 five_player_feasibility_20260927/capture_two_client_phase_20261011.py `
  --pid <PID> --phase host_before --output-dir <DIR>
```

随后按 `joined`、`after_leave`、`migration_before`、`migration_after`、`cleanup` 各执行一次。

两人测试流程：

1. `host_before`：房主单独在船上，`peer_count_raw=1`。
2. `joined`：第二人加入同一房间，`peer_count_raw=2`，网络索引为 `0` 和 `1`。
3. `after_leave`：第二人退出，人数回到 `1`，退出者的 peer 和 roster 槽位释放。
4. `migration_before` / `migration_after`：房主退出前后，原客户端成为房主，旧房主 peer 消失。
5. `cleanup`：会话结束后人数和 roster 都清零。

先只验加入和人数变化：

```powershell
python five_player_feasibility_20260927/verify_two_client_lifecycle_20261011.py `
  --scope join `
  --snapshot host_before=path\host_before.json `
  --snapshot joined=path\joined.json `
  --output output\two_client_join_receipt.json
```

完整两人生命周期需要再传入其余四个阶段：

```powershell
python five_player_feasibility_20260927/verify_two_client_lifecycle_20261011.py `
  --scope full `
  --snapshot host_before=path\host_before.json `
  --snapshot joined=path\joined.json `
  --snapshot after_leave=path\after_leave.json `
  --snapshot migration_before=path\migration_before.json `
  --snapshot migration_after=path\migration_after.json `
  --snapshot cleanup=path\cleanup.json `
  --output output\two_client_lifecycle_receipt.json
```

通过 `join` 或 `full` 都不会把容量验收改成两人。`capacity_above_two_verified` 始终为 `false`；5–8 名独立客户端仍然需要单独的实时证据。
