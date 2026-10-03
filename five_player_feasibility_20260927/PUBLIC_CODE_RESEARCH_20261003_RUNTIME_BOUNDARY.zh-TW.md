# Public runtime research: HD2Runtime and ReinforcementBeaconsFixed (2026-10-03)

## Scope

固定读取两个公开仓库的当前 `main/master`，只研究它们能否提供八人同任务所需的 Session → peer admission → Player Clone 入口；不把普通数据写入或 Mod Options UI 当作网络容量证据。

| Repository | Commit | What it provides | Eight-player decision |
|---|---|---|---|
| [SkyeShade/HD2Runtime](https://github.com/SkyeShade/HD2Runtime) | `96ab2d258d867a5df4f22bb7b3321d84d28de21d` | Bingus Shared Loader runtime；guarded patches/transactions/plans、语义化武器/战略配备/实体数据与事件接口 | 可作为版本门控、数据层事务和诊断依赖；公开能力没有 Party、Lobby、GameSession、confirmed-peer、player-slot admission 或 Player Clone 建立接口 |
| [CowboyBingus/ReinforcementBeaconsFixed](https://github.com/CowboyBingus/ReinforcementBeaconsFixed) | `daec6559a28bf287d716ee4dc3afe5d2e1f314b6` | build `25480438` 的 Lua 数据模块；修改既有增援队列字段，使用 Shared Loader | 可作为逐客户端安装和回滚日志模式参考；它明确不改 executable、不改变其他玩家或网络状态，不能扩展玩家容量 |
| [CowboyBingus/ModOptionsMenu](https://github.com/CowboyBingus/ModOptionsMenu) | `46d693e421b44c4221ee6d984d26ea49997b948a` | build/hash/entry gate 与 Mod Options UI | 只用于诊断开关和受保护配置，不作为容量或 admission 证明 |

## Evidence boundary

HD2Runtime README 将能力集中在 guarded data authoring、transactions、plans 与事件脚本；不提供 Session/Party/peer writer。ReinforcementBeaconsFixed README 明确只改当前玩家的已有增援队列数据，并要求每个客户端安装，且不修改 executable instructions。故 Lua/Shared Loader 路线不能单独完成第五至第八名的加入、角色建立、entity replication 或任务生命周期。

## Implementation impact

1. 保留 runtime/ModOptions 作为 fail-closed 的版本门控、诊断面板和数据层辅助。
2. 不再为八人容量继续扩展 Lua data writer；原生工作集中在 `0x108C18F` host capacity、`0x108C3D8` allocator、`0x108C760` confirmed-peer sender、`0xB90B20` client insert、`0x1086460` player creation gate 及其 cleanup/migration 链。
3. 公开仓库的“每个客户端安装”结论只适用于数据修改；八人 Mod 仍需 host/client 同版本的 native bridge，不能据此假定 host-only 可行。

## Stop condition

已得到公开仓库的当前 commit、能力范围和安装边界；它们没有提供可复用的八人 admission ABI。因此停止把这些仓库作为原生网络突破候选，回到固定 build 的 native callback、owner lifetime、资源回滚和真实多人验证。

`capacity_proof=false`, `player_admission_proven=false`, `player_creation_proven=false`, `installable=false`, `multiplayer_verified=false`。
