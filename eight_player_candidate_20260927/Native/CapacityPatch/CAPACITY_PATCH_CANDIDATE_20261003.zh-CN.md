# 八人容量原生补丁候选（2026-10-03）

新增 `eight_player_capacity_pluginw64_release.dll`，透过已验证的官方 Stingray plugin ABI 进入游戏。它不是只改一个 `MAX_PLAYERS`：会在固定 `Build 25480438` 上，对 35 个已保存的四人容量／枚举／加入／状态更新立即数做统一版本指纹检查，再以一次事务写入 `8`，任一位置不匹配即全部拒绝。成功写入后刷新指令缓存；插件卸载时尝试恢复原 bytes。

## 启用方式

默认关闭。只有明确设置 `EP_ENABLE_CAPACITY_PATCH=1` 才会写入。日志路径由 `EP_CAPACITY_PATCH_LOG` 指定。未设置时插件只记录 disabled，不写游戏程序。

机器清单：[capacity_patch_manifest_20261003.json](capacity_patch_manifest_20261003.json)

## 已完成

- 固定 `game.dll` SHA-256、25 个 RVA、原始 bytes 和替换 bytes。
- 事务式 preflight：先验证全部 site，再进行任何写入。
- 每个写入点使用 `VirtualProtect`、`FlushInstructionCache`，卸载时按逆序回滚。
- Visual C++ x64 DLL 构建通过；合成替换测试通过。

## 仍未闭合

这只解决已确认的四人硬编码层，不能伪造 Party/PlayFab 成员，也不能直接创建 confirmed-peer、Player Clone 或客户端实体。原生 inline member storage 与相邻控制字段仍存在冲突，因此本插件暂不标记为可安装或多人完成。下一步必须在固定 build 上先记录真实第五 peer 的 admission／creation 回调，再把 sidecar、cleanup 和客户端同步接入同一事务。
