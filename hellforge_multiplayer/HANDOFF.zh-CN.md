# HellForge 多人项目交接

更新：2026-10-25（Asia/Taipei）。这是当前主线；`github_handoff_20260927` 保存旧交接与证据。旧完整目标文件继续保留原始字节，最终八名真人同任务的验收要求不降低。

## 这次迁移改变了什么

原来的第一阻碍是官方运行环境中 Party wrapper 的共同 dispatcher 与调用栈契约。HellForge 0.2.0-beta 的源码已经提供 `native/sdk-shims/party_shim.cpp`、`lobby_shim.cpp` 和 `src/HellForge.LocalBackend/Multiplayer/`。当前先从这些源码接口推进，旧 dispatcher 补充采样退为历史路线，不再列为 HellForge 源码工作的前置条件。

这不证明 HellForge 的全部 ABI、游戏内玩家结构和八人同步已满足。SDK shim 的源码接口与真正游戏角色的生命周期是两层。

| 原项目部分 | HellForge 路径或迁移决定 |
|---|---|
| `Native/CapacityContract` | 原样复制进 `mod/src/core/`，来源及 SHA-256 固定在 lock；继续拒绝超出已证明上限的请求 |
| Loader / Lua 启动入口 | 新的 `hellforge_mod_init` 与 SDK 13 清单，不复用旧加载器安装脚本 |
| Party wrapper/dispatcher 分析 | 保留历史；优先研究上游 `party_shim.cpp` 与 `PartyService.cs` |
| Session/接纳 | 对照 `lobby_shim.cpp` 与 `LobbyService.cs`；八节点测试只证明服务层处理，不改游戏发出的容量 |
| `Native/CapacityControl`、`Bridge`、`Sidecar` | 保留旧实现供复用；目前没有绑定到 HellForge 的真实 provider |
| 玩家创建、控制、复制、增援 | 仍需游戏内容器/网络索引适配；不能由 SDK 生成事件代替 |
| 离开/重连 | 结合上游 `netreap.c`；本轮仅验证后端的清理和重连，未执行 native reaper |
| 实机与发布门槛 | 全部保留：安装整合、单人/两人、第五人、八人完整流程逐项证明 |

## 已查实的容量边界

固定上游 commit：`a4dd089eb56cdd5cd96c3cefe6e80eba5848d6fa`。

1. `LobbyService.cs` 创建房间使用请求的 `maxMembers`；加入时检查模组、协议、锁和成员数。内存后端测试能够创建八成员房间，拒绝第九个成员。
2. `PartyService.cs` 使用动态节点/端点集合，按房间成员资格接纳 Party 连接。测试验证了八端点路由与端点块重用。它转发 `maxUsers/maxDevices` 配置，不应把“配置回传一致”解读为已经完整实现各项 SDK 容量约束。
3. `native/mod-loader/event_sources.c` 定义 `EVT_MAX_PLAYERS 4`；`PollPlayers` 超过四人直接返回。`event_polls.c::EvpPlayers` 同样拒绝超过四人。
4. 这些代码的玩家记录为 `manager + 0x2C8 + 0x38*i`，avatar 网络表为 `manager + 0x3A8 + 0x20*i`。根据源码偏移计算，第五条玩家记录起点 `0x2C8 + 4*0x38 = 0x3A8`，与另一张表相交。因此只把 `EVT_MAX_PLAYERS` 改成 8 会把邻接字段当成玩家记录，不能视为正确扩容。
5. 上游明确将房主退出处理为关闭房间；这轮模拟后端验证相同行为，不宣称房主迁移成功。

## 继续实施顺序

1. **玩家存储适配**：将既有 Sidecar/Bridge 的权威索引、归属和清理契约逐项映射到 HellForge 所用游戏构建。列出所有固定四项数组及创建/遍历/删除消费者，设计统一外部存储接入，避免只改变数量字段。
2. **引擎扩展边界**：如需替换上游事件枚举，准备固定 commit 的引擎补丁与合成内存测试。先支持可注入、可撤销的玩家列表 provider，再讨论第五槽，不能原地扩大四项结构。
3. **容量事务**：通过有明确生命周期的 native provider，将房间、Party、peer、roster、entity、资源及复制容量作为一个事务提交；失败可回滚，客户端相容性必须检查。现有 SDK 没有可直接完成这一事务的“set_max_players”调用。
4. **生命周期与同步**：加入、角色创建、控制权、复制、死亡/增援、离开/重连、撤离与清理分别测试；与 HellForge 的 hook 链及 netreap 协作。
5. **实机验证**：仅在新的明确授权后进行。先两台电脑各一个客户端，再第五人，最终八个独立账号完整任务。离线八节点从不算真人或游戏客户端。

## 验证及重现

入口见 [README](README.zh-CN.md)。`evidence/offline-validation.json` 记录两组实际执行的测试和产物指纹。原始容量核心逐字节相同；上游源码无改动；新接入层使用真实 SDK 头编译，但测试的 SDK 回调均为模拟值。

不执行上游 `Launch.cmd`、`Build-Engine.ps1`、`Publish-HellForge.ps1` 或 setup：前者会启动应用，后两种流程可能寻找并读取已安装游戏、生成 stand-in 或写入安装目录。这轮只调用本项目显式限定的源码构建入口。

运行授权：`live_capture_authorized=false`、`game_install_authorized=false`、`game_launch_authorized=false`。PID 30776 的旧一次 v2 采样已消费，剩余 0。旧证据、上传收据和 2026-10-19 快照不改写为 HellForge 实测。
