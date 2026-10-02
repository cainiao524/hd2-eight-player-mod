# 公開 runtime / loader 與八人 native bridge 核對

日期：2026-10-02  
固定目標：Steam build `25480438`、EXE `1.8.46015.0`。  
證據邊界：只核對公開 checkout、文件和檔案雜湊；沒有複製第三方原始碼進 Mod payload，也沒有用這些來源宣稱第五至第八名玩家成功。

## 結論

本輪沒有找到可直接接到目前 native plan 的公開 `confirmed-peer`、`player creation` 或八槽 cleanup bridge。最有價值的新來源是 [SkyeShade/HD2Runtime](https://github.com/SkyeShade/HD2Runtime) v0.28.1（commit `96ab2d258d867a5df4f22bb7b3321d84d28de21d`）。它與 [Better Lobby Management](https://github.com/CowboyBingus/BetterLobbyManagement) v1.1（commit `5294433adf83c8bcf7e0c131ea8344df727ae2ca`）都明確鎖定本專案的 EXE/game.dll hash，但兩者都把玩家／事件讀取限制在四名玩家；HD2Runtime 還明確把通用網路 entity spawn 列為 blocked。

可重用的是「同版版本 gate、唯讀觀察、已驗證 native call 的小型 adapter、日誌與失敗隔離」；不能重用為八人 admission。完整 commit、來源檔案 SHA-256 和判定保存在 [PUBLIC_RUNTIME_BRIDGE_RECEIPT_20261002.json](PUBLIC_RUNTIME_BRIDGE_RECEIPT_20261002.json)。

## HD2Runtime：同版唯讀 player/event reader

來源：`SkyeShade/HD2Runtime` v0.28.1，commit `96ab2d258d867a5df4f22bb7b3321d84d28de21d`。

`domains/event_natives.lua` 的 current profile 含：

- `players.global = 0x3326340`、`count = 0x84`、`peers = 0x2C8`、`peerStride = 0x38`、`maxPlayers = 4`；
- `stats.maxPlayers = 4`；
- source 中固定 `game.dll` SHA-256 `2e2c3b7c...18f51e`，與本專案相同；同時記錄 `game.dll` image size `74727424` 和 EXE image size `60719104`，但不提供 EXE SHA-256。EXE SHA-256 `f5fee03d...00d5f06` 來自本專案的固定版本指紋，不冒充 HD2Runtime 檔案內的證據。

`runtime/event_world.lua` 的 `players()` 先讀 count；若 count 大於 `P.maxPlayers`，直接回傳空清單。它可觀察 peer id、lifecycle、player descriptor、avatar network id 和 network-id map，但沒有 writer、slot migration 或 resource cleanup。

`runtime/windows_write.lua` 的 native adapter 是嚴格白名單：先由 caller 重核對 prologue，再呼叫 heal、explosion、projectile、status 等已知 gameplay function。檔案中沒有 Session、Party、confirmed-peer、player creation 或 host migration 的 ABI。

`api/hd2.lua` 將 generic `spawn_entity` 標成 blocked，理由是 spawn 參數與網路 replication 未證明。這與目前 `0x1086460` player-creation gate 的缺口直接相符：能觀察既有角色，不代表可以創建 network index `4..7` 的角色。

## Better Lobby Management：同版 session layout 與 Lua native 方式

來源：[CowboyBingus/BetterLobbyManagement](https://github.com/CowboyBingus/BetterLobbyManagement) v1.1，commit `5294433adf83c8bcf7e0c131ea8344df727ae2ca`。

`src/game.lua` 公開了本次固定 build 的 session layout：

| 欄位 | 值 | 意義 |
|---|---:|---|
| `CONTEXT_PTR` | `0x347cef0` | network context |
| `PEER_COUNT` | `0x16390` | peer count |
| `PEERS` | `0x16398` | peer record 起點 |
| `PEER_STRIDE` | `32` | peer record stride |
| `PEER_INDEX` | `20` | record 中的 network index |
| `MAX_PEERS` | `4` | Lua reader 的容量上限 |
| `ROSTER_PTR` | `0x347ced8` | persona roster |
| roster record | `0xC0`、4 筆 | persona name／peer id 讀取 |

`src/windows_api.lua` 展示了 LuaJIT FFI 的 `api.native(type,address)`、module SHA-256、guarded read 和既有 private data write。這是可以借用的觀察與診斷模式；它沒有 `confirmed-peer` ABI，也沒有把 `MAX_PEERS` 替換成 8。其 lobby 操作沿用遊戲自身 kick、join 和 host migration，所以不能證明額外 player entity 可建立。

## ReinforcementBeaconsFixed 與 Bingus loader

`ReinforcementBeaconsFixed` v4.5（commit `daec6559a28bf287d716ee4dc3afe5d2e1f314b6`）的 `src/spawn_data.lua` 對 current player manager 明確 `assert(count <= 4 and available <= 4)`。它示範 build hash、snapshot reread、single write、verify 和 rollback；這些是資料修改生命週期，不是 session capacity bridge。

`BingusSharedLoader` v18（commit `3d7e3a120828178573ef1ee0a5c7eeae4a951865`）提供 API 1、addon discovery、shared logs 和 module failure isolation。其 technical notes 明確把 loader 描述為啟動／模組協調層，沒有 process-memory peer/session writer。八人 native payload 若有一天完成，仍需獨立的版本化 bridge 與安裝／回滾出口。

## 與本地 native plan 的映射

| 本地 root | 公開來源能提供的部分 | 尚缺的 production contract |
|---|---|---|
| `0x108C18F` capacity gate | 同版 hash gate、讀取與 log 模式 | mid-function continuation、stack/register/unwind、回滾安裝 |
| `0x108C3D8` index allocator | 四槽 layout 的觀察結果 | 八槽 owner storage、allocator flags、失敗回復 |
| `0x108C760` confirmed-peer sender | BetterLobby 的 peer/index reader；HD2Runtime 的 player observer | 五欄 sender callback、event hash dispatch、host/client resource lifetime |
| `0xB90B20` client insert | HD2Runtime 能讀既有四筆 player records | `client+0x150` 鄰區衝突、append/remove/reset/readers 的八槽改接 |
| `0x1086460` player creation | HD2Runtime 明確拒絕未證明 generic spawn | index `4..7` 的 resource handle、component/roster binding、角色 cleanup |
| departure／host migration | BetterLobby 使用遊戲自身 kick／migration，作為四人行為參考 | 八槽 departure、reconnect、package unload、stale handle 清理 |

`PUBLIC_RUNTIME_BRIDGE_RECEIPT_20261002.json` 對每一列來源保存 commit、檔案大小和 SHA-256，避免將未鎖定版本的網路文章或複製程式碼當作 ABI 證據。

## 目前判定

- 找到的公開程式碼可支援 **固定 build 的唯讀診斷器**、玩家／事件觀察器、hash gate、日誌與 package 分發。
- 沒有找到可以直接安裝的 `confirmed-peer → player creation → cleanup` 八人 bridge。
- 本地 `native_peer_admission_plan_20261002.json` 必須維持 `executable=false`；這份公開核對不能把 synthetic sidecar、HD2Runtime 觀察器或 BetterLobby 四人功能提升為多人成功。
- 下一個強證據仍是固定 build 的 diagnostics run：在真實第五名 peer 上記錄 host sender、client insert、player creation、resource handle、離隊／重連與 cleanup 的完整順序，再決定是否能把 callback 接到 native bridge。
