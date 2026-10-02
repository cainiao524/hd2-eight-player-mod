# 公開執行入口能力審計（2026-10-03）

本紀錄只讀工作區已保存的公開倉庫快照與既有 `25480438` 擷取資料。沒有開啟遊戲程序、沒有安裝或修改 Mod、沒有寫入程序記憶體，也沒有進行多人測試。它用來界定下一個真正實作閘門，不是八人可玩證明。

## 可重跑驗證

從倉庫根目錄執行：

```text
python five_player_feasibility_20260927/public_runtime_entry_audit_20261003.py --write
```

預期輸出：`PUBLIC_RUNTIME_ENTRY_AUDIT_OK`。驗證器會重新讀取所有固定來源、逐檔計算 SHA-256、解析 RawData 與舊型別、並從 `captured-data.bin` 重新取出兩段 native bytes。固定收據位於 `public_runtime_entry_audit_20261003.receipt.json`。

固定遊戲指紋：Steam build `25480438`、EXE `1.8.46015.0`、`game.dll` SHA-256 `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e`、EXE SHA-256 `f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06`。

## 已找到、但用途有限的入口

### HD2Runtime 玩家清單讀取器

`HD2Runtime/domains/event_natives.lua` 的目前 build profile 明確記錄 `players.maxPlayers = 4`、`peerStride = 56` 與玩家管理器欄位。`runtime/event_world.lua` 的 `M.players` 只讀取 count、peer record、descriptor、lifecycle 與 avatar network ID，再透過 network-ID map 解析實體；count 大於 profile 上限時直接回傳空結果。`docs/events.md` 將 `HD2PlayerHandle` 定義為 peer 已存在於 player list 時有效的觀察 handle。

因此這是可重放的四人觀察路徑，不是 `Session/Party/confirmed-peer/player-creation` writer。它沒有提供第五至第八個 peer 的 admission、slot insertion、角色建立或 cleanup ABI。

### 可逐 byte 核對的 package ABI

`HD2Runtime` 對本機 `RefcountedPackageSystem` 有已固定的 request/release bytes：

| 項目 | 值 |
| --- | --- |
| request RVA | `0x12FE350`（384 bytes） |
| release RVA | `0x12FE4E0`（384 bytes） |
| instance global | `0x347CEB0` |
| request 形式 | `void(instance, const uint64_t*, uint32_t count)` |
| engine load vtable slot | `+0x2F0` |
| engine unload vtable slot | `+0x300` |
| 擷取資料 SHA-256 | `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d` |

驗證器已從既有擷取逐段重新取得 request/release bytes，兩段均與 `package-residency-F5FEE03DCFDB.json` 相符。這個 ABI 的作用是讓本機 loadout/資源 package 常駐，不能代替 PlayFab/Party admission，也不能建立遠端玩家或 network entity；報告將它標成 `supported_local_asset_only`。

## RawData 的 Player 與 Avatar 必須分開

目前 `Darctor/Helldivers2_RawData` 的 `EntityComponentMap` 有兩筆不同資源：

| 資源 | Hash | 元件數 | 觀察 |
| --- | --- | ---: | --- |
| `content/entities/player`（邏輯玩家/船資料） | `14826404319954434690` | 9 | 含 ShipCustomization、ShipModulesSync、KillStreak、ShipInventory、Weathering 等 |
| `Player Clone (Avatar)` | `5556372446766824087`（`0x4D1C334D294DFA97`） | 49 | 含 Avatar、Inventory、Voice、Stance、Animation、Health、Locomotion 等角色元件 |

舊 `shalzuth/HelldiversData` map 也為兩筆資源列出不同 component ID。`EntityNetworkDataArray` 的 schema 是 `array<EntityNetworkData>`，`NetworkOverrideComponent` 的公開資料只有 dummy 欄位；這些都是 schema 參考，不是容量或 admission 證明。把 9 元件的邏輯玩家資源誤當成 49 元件的 Avatar，會導致錯誤的八人實作路線。

## 其他公開倉庫的邊界

* **Better Lobby Management**：公開 `game.lua` 固定 `ROSTER_PTR` 為 4 個 `0xC0` roster、`MAX_PEERS = 4`、`PEER_STRIDE = 32`。技術文件說明正常 KICK 由遊戲自己的路徑處理；公開 native wrappers 是既有加入/踢出操作，沒有 confirmed-peer append 或容量擴展 ABI。
* **Bingus Shared Loader**：只做 Lua 資源 discovery、`can_get` 與 `require`。技術文件明確寫出 loader 不寫 process memory，也不能建立 multiplayer compatibility。
* **CChusky/hd2-tools**：README 的共享記憶體通道是 entity/raycast capture。快照中的 `watcher.c`/`dll_injector.c` 含 `OpenProcess`、`WriteProcessMemory`、`CreateRemoteThread` 的注入路徑；這不符合本輪只做離線研究的前提，且程式碼中沒有 peer/roster admission writer，不能當成安全的八人入口。

公開來源：

* [BingusSharedLoader](https://github.com/CowboyBingus/BingusSharedLoader)
* [hd2-tools](https://github.com/CChusky/hd2-tools)
* [Helldivers2_RawData](https://github.com/Darctor/Helldivers2_RawData)
* [HelldiversData](https://github.com/shalzuth/HelldiversData)
* [HD2Runtime](https://github.com/SkyeShade/HD2Runtime)
* [BetterLobbyManagement](https://github.com/CowboyBingus/BetterLobbyManagement)

## 實作結論與下一個閘門

本輪沒有從公開快照找到可呼叫的 peer admission、第五至第八個 `player index` 分配、confirmed-peer 建立、或跨客戶端 player-entity spawn ABI。`public_peer_admission_abi_found`、`public_player_creation_writer_found`、`public_network_spawn_writer_found` 均為 `false`，八人狀態為 `unverified`。

因此目前可安全重用的只有：

1. 版本指紋與 fail-closed 的玩家觀察 reader；
2. 本機 loadout package residency request/release ABI；
3. RawData/舊 schema 作為型別與驗證參考。

要繼續做八人，下一個必要閘門是取得具授權的、同一 build 的 `Session/Party -> peer admission -> player creation -> cleanup` 實際呼叫鏈，逐項補齊 host/client、離隊、重連與 host migration。未找到該鏈以前，不應把四人 reader、動態 entity schema、或 package ABI 宣稱為八人 Mod。
