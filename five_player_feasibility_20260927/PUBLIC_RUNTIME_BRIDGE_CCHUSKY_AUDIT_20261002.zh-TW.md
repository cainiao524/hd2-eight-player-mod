# CChusky/hd2-tools runtime bridge 核對（2026-10-02）

固定目標：Steam build `25480438`、EXE `1.8.46015.0`。來源 checkout：`CChusky/hd2-tools`，commit `5d509fad01ce4d16465d991363d30cb4a4f47dfe`（`v1.0.3`）。完整檔案雜湊、命中行和判定在 [PUBLIC_RUNTIME_BRIDGE_CCHUSKY_RECEIPT_20261002.json](PUBLIC_RUNTIME_BRIDGE_CCHUSKY_RECEIPT_20261002.json)。

## 實際找到的入口

`hook/hd2_raycast_hook.c` 的入口是 LuaJIT `lua_pcall` x64 inline hook；仓库提供 `hook/build_clean.bat`，但本次审计环境没有 MSVC 工具链，因此没有把“有构建脚本”说成“本地已编译通过”。（`install_hook` 約第 463 行、安裝約第 3872 行），並在隔離 Lua thread 上執行 bounded entity/raycast probe。Numpad1 路徑讀取 `World.units`，以 `World.entities` 作 fallback，將 entity label、幾何和相機資料寫入 `Local\HD2RaycastShm`。這可作同版診斷觀察器的參考；它不會建立網路 peer，也不會產生 replicated player entity。

`hook/watcher.c` 和 `hook/dll_injector.c` 有 `OpenProcess`、`VirtualAllocEx`、`WriteProcessMemory`、`CreateRemoteThread`，用途是把 raycast DLL 注入遊戲。這些函式沒有 confirmed-peer、player creation 或 cleanup 參數，也沒有 25480438 的 EXE/game.dll hash gate；因此不納入交付 Mod 的 native bridge。

## 明確缺口

對 `hd2_raycast_hook.c` 進行固定字串與程式路徑核對後，沒有找到：

- confirmed-peer sender/receiver 或 peer index 分配；
- roster／player-manager 建立、移除、重連或 host migration；
- `player index = 4..7` 的 player creation、resource handle 綁定或 network replication；
- departure／package unload 的玩家資源清理 callback。

檔案中的 `player` 文字只出現在 entity/raycast 說明（例如 `World.units` 包括 dynamic player units），不能作為角色生命週期橋接證據；cache/crash-skip 的「cleanup」也與 peer/player cleanup 無關。

## 採用決定

- **可重用：** bounded Lua observer、`lua_pcall` hook 的隔離與共享記憶體診斷形狀；接入前仍須補同版 hash gate、owner/thread quiescence、卸載回滾。
- **不可重用為八人 bridge：** injector、raycast-specific Lua path、entity label/mesh pipeline；它們没有 session admission、confirmed-peer、player creation 或 cleanup ABI。
- `installable=false`、`live_ready=false`、`multiplayer_verified=false` 保持不變。该核对没有修改游戏文件，也没有执行注入或多人测试。

下一個有價值的動作是把此類 observer 接到本地 diagnostics frame ring，在真实第五名 peer 流程中记录 host sender、client insert、player creation 和 cleanup；在没有这些 runtime 事件前，不应把 Lua hook升级为八人候选。
