# Capacity Patch Peer 观测修正（2026-10-03）

`live_capacity_patch_runtime_20261003_peer_slots.jsonl` 保存了一次旧探针的原始记录。该探针把公开 `GameSessionCApi` 的 `peer()`/`num_peers()` 偏移直接套到 HD2 的 runtime table；之后的固定 build vtable capture 显示这些 wrapper 的实际下游布局没有完成语义绑定，其中若干函数包含修改 session 状态的代码。旧记录中的 `peer_count=0..16` 以及八个相同槽值不能作为只读 peer 或玩家数量证据，报告因此固定 `peer_id_semantics_unresolved=true` 并标记为 superseded。

修正后的 `CapacityPatch` 不再调用这些函数，只读取已固定机器码的 Network `game_session` getter，并记录 session 指针。新增 `Native/SessionObservation/ep_session_snapshot.h` 已对齐现有四人基线工具：它核对 `game.dll` PE identity，从 `game.dll` 的 context/roster/game-state globals 读取已知字段，再稳定重读最多八个 peer record，以及四个有文档依据的 inline roster record。它不把 roster slot `4..7` 当成已确认布局，也不解码 confirmed-peer raw window。超出八个、索引越界或重复、缺失字段及重读变化都 fail-closed。`ep_session_snapshot.exe` 已通过稳定读取、九人拒绝、重复索引拒绝和版本不匹配拒绝测试。

这项修正提高了观测安全性，但没有提供 Party/PlayFab admission、第五至第八个 Player Clone、实体复制或多人任务证明。`player_admission_proven=false`、`player_creation_proven=false`、`installable=false`、`multiplayer_verified=false` 保持不变。
