# 公開程式碼與研究核對：八人 Mod 的實際方案

**核對日期：2026-10-02**  
**目標：**八個獨立帳號、八名真人、同一任務、可安裝 Mod。  
**證據邊界：**本報告只整理公開程式碼、公開資料與公開研究；沒有存取遊戲程序，也沒有把離線模擬或四人回歸算成多人成功。

## 結論

目前沒有找到已公開、已驗證能把 Helldivers 2 提高到五至八名玩家同一任務的成品 Mod。公開資料比較支持以下判斷：底層資料庫和 PlayFab/Party API 可能有較大的通用容量，但現行遊戲在多個本機資料結構、加入流程、玩家索引、UI／roster 和任務邏輯仍明確使用四人假設。真正可行的路線是先解決 **session 接納 → peer/index 發布 → client confirmed-peer → player 建立 → 八格 roster／元件 → hot-join／離隊 → AI／UI** 的整條鏈，不能只把 `MaxPlayers` 或一個比較值改成 8。

第一個可驗證目標仍應是 **第五名玩家全流程**。如果第五名只能加入 PlayFab lobby、不能在 game.dll 的 peer list 和 client player record 中得到唯一 `player index = 4`，後面的 EntityNetworkData 或 Player Clone 候選都沒有作用。

## 公開來源與可用結論

| 來源 | 公開內容 | 對八人方案的用途與限制 |
|---|---|---|
| [Arrowhead FAQ](https://arrowhead.zendesk.com/hc/en-us/articles/12571604061212-Helldivers-2-FAQ) | 2026-09-24 更新的官方說明仍寫每 squad 最多 4 人。 | 這是現行產品契約基線；任何 8 人 Mod 都是在改變官方未支援的路徑。 |
| [Better Lobby Management README](https://github.com/CowboyBingus/BetterLobbyManagement/blob/main/README.md) 與 [game.lua](https://raw.githubusercontent.com/CowboyBingus/BetterLobbyManagement/main/src/game.lua) | 針對 Steam build 25480438 / EXE 1.8.46015.0 的公開 Lua 逆向程式碼。`MAX_PEERS = 4`、`ROSTER_PTR` 是 `4 x 0xC0`，peer list 是 count 加 32-byte entries，entry `+20` 是 player index。 | 這是目前最直接的公開 session／roster 證據：至少這些本機 wrapper 不是動態八格。它不是 Arrowhead 原始碼，應視為同版 reverse-engineered layout；但與本機 `game.dll` 四槽結果相互印證。 |
| [Better Lobby Management technical notes](https://raw.githubusercontent.com/CowboyBingus/BetterLobbyManagement/main/docs/TECHNICAL.md) | 公開 `[0x347CEF0]` network context：local/host peer、join component、PlayFab lobby wrapper、member count、peer count、32-byte peer entries；也記錄 host-only promote、party Quickplay、privacy／room 檢查。直接呼叫 remove/kick 曾造成客戶端未離場後的資源卸載 crash，必須讓遊戲自己的 player-menu KICK 完整執行。 | 提供 P1 的具名觀測點、非同步完成條件與清理順序。加入擴容時應沿用原生事件／cleanup 時序，不能從 Lua 直接呼叫移除。 |
| [FileDiver type-name catalog](https://raw.githubusercontent.com/xypwn/filediver/master/hashes/dl_type_names.txt) | 公開去 hash 型別名包含 `EntityNetworkDataArray`、`EntityNetworkData`、`NetworkOverrideComponent`、`ShipTeleporterComponent(Data)`；也有 `CutsceneId_ship_teleporter_deeplink_join` 與 `...network_join`。 | 證明使用者分析抓到的名稱確實存在於公開 HD2 data-library catalog，並支持 hot-join／network-join 是獨立路徑；但 catalog 沒有 native 欄位、容量或 allocator，不能從名稱推論可容納八名玩家。 |
| [OTL Patrol research](https://helldiversotl.com/research/patrols) | current 7.1.0 的 Patrol consumer 仍按 active Helldiver count 使用 1P=1.00、2P=1.25、3P=1.45、4P=1.60；選組也按 player count 和 current population 過濾。 | AI Director 有真正的 1–4 依賴。5–8 的值、clamp、fallback 或越界行為仍需同 build asset／consumer audit；不能把 4 人最後一項直接當成已證的八人平衡。 |
| [Patch 01.001.201 notes](https://patchtracker.gg/helldivers-2/patch-01-001-201) | 官方修過「四人 party 有人離開後 Quickplay 才能加入」、玩家 join/leave soft-lock、mission summary hot-join soft-lock，以及避免加入已滿 lobby。 | 這些修正說明 hot-join、full-lobby、mission-summary、離隊清理是獨立風險面；第五人測試不能只測 lobby invite。 |
| [2024 FindLobbies packet observation](https://www.reddit.com/r/Helldivers/comments/1cugtwc/technical_discovery_helldivers_2_can_on_paper/) | 社群擷取看到 FindLobbies 回應的 `MaxPlayers` 一直是 8，但原作者同時明說遊戲沒有使用八人，實際 lobby cap 仍是 4。 | 這只能當作平台欄位的線索，不能當作八人 mission 證據。 |
| [2026 lobby-expansion WIP](https://www.reddit.com/r/HelldiversUnfiltered/comments/1wto5j1/vibe_coding_for_lobby_expansion_more_than_4/) | 近期公開 WIP 列出 PFMultiplayer/Party symbols；直接改 PartyWin.dll／PlayFabMultiplayerWin.dll 曾在啟動、進船或第五人加入時 crash，尚無 release。 | 與本機優先順序一致：DLL／平台層不是單一修補點。這是未驗證進度，不是可採用方案。 |
| [Bingus Shared Loader technical notes](https://github.com/CowboyBingus/BingusSharedLoader/blob/main/docs/TECHNICAL.md) 與 [HD2Runtime](https://github.com/SkyeShade/HD2Runtime) | 公開 shared Lua loader、guarded gameplay API、日誌、版本／bytes 檢查；loader／runtime 主要做 addon 啟動和 gameplay data authoring，沒有 player-cap API。 | 可作為候選 Mod 的安全載入、版本拒絕、診斷和封裝基礎；不能代替 session／native roster 修補。 |
| [Reinforcement Beacons Fixed](https://github.com/CowboyBingus/ReinforcementBeaconsFixed) | 公開資料型 gameplay mod：每個 diver 都要安裝才會修正自己的資料；離線 regression 與 solo live 已有，installed multiplayer 仍待驗證。 | 這是「host-only／all-client 行為必須逐項證明」的現成 HD2 例子，不是八人擴容。 |
| [HD2SDK Community Edition](https://github.com/Boxofbiscuits97/HD2SDK-CommunityEdition)、[HD2 Modding Wiki](https://boxofbiscuits97.github.io/HD2-Modding-Wiki/dev/sdk%20functions/functions.html)、[FileDiver](https://github.com/xypwn/filediver) | 公開資產提取、archive／unit／texture／component tooling。 | 能協助找資產、component type 和版本差異；沒有公開 session admission 或八人同步實作。 |
| [SteamDB depot 553853](https://steamdb.info/depot/553853/manifests/) 與 [depot history](https://steamdb.info/depot/553853/history/) | 公開列出 `dl_library.dl_typelib`、`generated_entities.dl_bin`、`game.dll` 等版本化檔案，且每次更新都可能變動。 | 逆向位址、schema 和 layout 必須綁定精確 Steam／EXE build；不能把不同版本的公開 layout 直接套用。 |

目前可下的公開 lobby 工具（[Better Lobby Management v1.1](https://github.com/CowboyBingus/BetterLobbyManagement/releases/tag/v1.1)、[Vanilla Plus Megapack v36](https://github.com/CowboyBingus/VanillaPlusMegapack/releases/tag/v36)、[Arsenal lobby coordination](https://docs.rsnl.gg/lobby)）都只改善 lobby 管理、房主交接、搜尋或 Mod 同步；沒有提高遊戲內玩家上限。[Arsenal 的 Mod Sync](https://docs.rsnl.gg/lobby/mod-sync) 是外部協調流程，不是 native roster patch。[LobbyGuard](https://www.nexusmods.com/helldivers2/mods/16768) 的 Nexus 頁面目前已標示 **Removed by staff**，不能列為現行可安裝依賴。

## 對既有本機證據的修正

公開 Better Lobby Management 的同版 layout 使目前 P1 判斷更明確：

1. `MaxPlayers = 8` 與 PlayFab lobby member count 不是同一層；前者即使能回傳 8，也不能證明 game.dll 接受第 5 名。
2. peer count／peer entry、4 筆 persona roster、player index 和 client confirmed-peer 必須一起追。只改 host admission 會讓第五名在平台上存在、但在 client 或角色建立層沒有完整身份。
3. public `NetworkOverrideComponent`、`EntityNetworkDataArray` 和 teleporter network-join 名稱支持「通用 entity／hot-join 層可能不是最先卡住」；它們沒有推翻已定位的四槽 native roster、join handler 和 player creation gate。
4. OTL 的 1–4 multiplier 使 P6 成為獨立必要工作。`94BE10` 的 player-count 候選不能自動視為 AI Director consumer 已修好。

## 實際八人方案

### Phase 0：建立診斷版，不先擴容

做一個同 build、fail-closed 的 diagnostics package，只讀並記錄：

- PlayFab lobby member count、max/member-lock、join result／拒絕原因；
- game.dll network context 的 local/host peer、peer count、每筆 peer id／player index；
- host confirmed-peer 發布與 client 接收事件；
- player creation gate 的輸入 index、resource call、返回 handle；
- roster／component 的 pointer、count、ordinal、owner、cleanup callback。

每個欄位要有 build hash 和 guarded read；未知版本只停用。Better Lobby Management 的 bytes gate、分段啟用和 log 方式可直接借用。

### Phase 1：第五人 admission prototype

先只做第五人，不同時動 AI、UI 和整個資料池：

1. 找到 game.dll join handler 的 capacity branch、host peer/large/pending arrays、client confirmed-peer record 的所有四筆配置。
2. 把 `player index = 4` 從接納到兩端確認通知連成一條可回滾的 candidate；保留原生 reject／unwind。
3. 讓第五人先在 lobby／ship 出現，再測進 mission；每次測試都確認第 5 筆 peer id、index、handle、entity、離隊和重新加入。
4. 如果 client 端必須持有擴容布局，先採 **八名客戶端同版本安裝**；只有完整證明 guest vanilla 也能接收時才考慮 host-only。公開 host-only lobby 工具不能外推到 player entity。

第五人通過條件不是「能看到第五個名字」，而是：相互可見、移動／射擊／互動、死亡／增援、離隊／重連、任務結算都沒有 stale peer、資源 unload 或 index 重用錯誤。

### Phase 2：八格 roster 和 player components

以目前 v0.14 的共同 B／八格候選為離線基礎，按實際 caller 清單完成：

- constructor／producer、receiver、registry、getter、arrival、departure、remove、compact／insert；
- 32-byte peer list 與 4 筆 persona roster 的每個 reader/writer；
- avatar、inventory、voice、stance、network override、loadout、metadata、rank、UI 和音效的固定容量或 dynamic ownership；
- 每個 pointer／count／ordinal／network index 的 missing、pending、reject、cleanup 行為；
- 不直接 call remove；沿用遊戲本身的 kick／despawn／package unload 次序。

### Phase 3：hot-join、teleporter 和任務生命週期

把 `network_join`／`deeplink_join` 的角色建立和現有 world state 同步拆開測：

- 任務開始前 5 人，再逐一加入到 8 人；
- 任務中途加入、有人死亡、有人離隊後再加入；
- mission summary、撤離、失敗、成功、回船；
- reinforcement、loot、animation、corpse repair、objective state 和 host migration。

每個階段保存 host 和各 client 的 session snapshot；只要一端的 peer index、resource handle 或 roster count 不一致，就回到診斷，不繼續加人數。

### Phase 4：AI、UI 和負載

先做安全的 5–8 行為定義，再決定平衡：

- AI Director 的 5–8 multiplier 先採明確 clamp/fallback，不能讓 array index 越界；
- player-count selection、shared enemy capacity、patrol／encounter budget 要記錄 5、6、7、8 的實際 consumer；
- squad UI、map marker、score、rank、stratagem ownership、reinforce queue 都要用 0–7 測試；
- 先以原 4 人敵人壓力跑同步穩定性，再另做八人平衡；不要把效能問題和 admission 問題混成一個 patch。

### Phase 5：交付與驗證階梯

交付版本應固定為：

1. 4 人未修改基線；
2. 5 人全流程；
3. 6 人全流程；
4. 7 人全流程；
5. 8 人全流程；
6. 退回 4 人、離隊、重連、房主離開、更新／移除 Mod。

每一關都要有同 build hash、安裝清單、host/client log、任務結果和 crash／stale state 檢查。沒有八帳號實際同任務記錄前，版本名稱只能是 `offline` 或 `prototype`，不能稱為八人完成。

## 目前最值得投入的三個工作

1. **P1：**沿著 public `network context → PlayFab member count → join handler → peer index → confirmed-peer` 補齊第五人結果，不再泛查 Player Clone。
2. **P2/P3：**把 `player index = 4` 的 client 接收、player creation 和 roster resource lifetime 串成可拒絕、可清理的 candidate。
3. **P6：**固定同版 AI Director player-count asset 和真正 consumer，先定義 5–8 的安全 fallback，再做平衡資料。

上述三項完成前，不應再增加更多「可能有八人」的 schema 名稱，也不應把 platform `MaxPlayers=8`、EntityNetworkDataArray 或 hot-join cutscene 當成可玩八人的證明。

## 依使用者優先級補充核對（2026-10-02）

本節是對使用者列出的十個公開倉庫做的實際 checkout 核對。每個快照的提交、分支和可用入口都記錄在同目錄的 [`PUBLIC_CODE_RESEARCH_20261002.manifest.json`](PUBLIC_CODE_RESEARCH_20261002.manifest.json)。研究只讀取公開原始碼與文件，沒有把任何倉庫的程式注入遊戲，也沒有把它們的單機或 loader 測試算作多人成功。

### 快速結論

| 優先級 | 倉庫與核對提交 | 可直接借用的部分 | 不能證明／主要風險 |
| --- | --- | --- | --- |
| S | [Darctor/Helldivers2_RawData](https://github.com/Darctor/Helldivers2_RawData) `52056ec` | `EntityComponentMap.json`、`HiveMindComponentData.json`、元資料中的 `game_version`／`patch_date`；可核對 component、AI player-count 陣列與 ShipTeleporter component | 沒有 native session／peer 程式碼；目前資料是 `1.007.100`／2026-09-22，未證明等同 Steam build 25480438；沒有倉庫授權檔，不能直接重發布資料或遊戲內容 |
| S | [shalzuth/HelldiversData](https://github.com/shalzuth/HelldiversData) `0d18368` | `data/components/EntityNetworkData*.json`、`NetworkOverrideComponent.json`、`ShipTeleporterComponent*.json`、`AnimationComponent.json`；可作舊型別對照 | 2025-09-20 的舊資料；AGPL-3.0 會影響衍生程式碼分發；型別 schema 不是 native capacity 證明 |
| S | [CChusky/hd2-tools](https://github.com/CChusky/hd2-tools) `5d509fa` / `v1.0.3` | `hook/hd2_raycast_hook.c` 的 x64 trampoline、Lua `pcall` hook、隔離 `lua_newthread`；`overlay/shm_proto.h` 的共享記憶體協定、entity 掃描和標籤管線 | 只有 entity/raycast 觀測，沒有 peer、roster 或 player creation；來源使用 DLL injection、`WriteProcessMemory`、遠端執行緒和 `NtOpenProcess` 旁路；PolyForm Noncommercial，且沒有目標 build SHA guard |
| S | [CowboyBingus/BingusSharedLoader](https://github.com/CowboyBingus/BingusSharedLoader) `3d7e3a1` / v18 | `src/shared_loader.lua` 的 API 1、模組 failure isolation、`open_log`；`src/discover.lua` 的宣告式 addon 發現；`scripts/build_addon.py` 的封裝方式；v18 明確支援 build 25480438 | 這是 Lua startup／addon loader，不是 session 或 peer API；沒有 repository-wide license；Wwise resource ownership 和 manager priority 仍須保持；只可作診斷、日誌和封裝基礎 |
| A | [xypwn/filediver](https://github.com/xypwn/filediver) `7b52b32` / `v0.7.57` | `app.OpenGameDir`、`App.MatchingFiles`、`App.ExtractFile`；`datalibrary.ParseTypeLib`、`ParseEntityComponentSettings`、`ParseEntityDeltas`；`stingray.entity.LoadEntity`；`hashes/dl_type_names.txt` | 只處理 archive／DataLibrary／typelib，沒有 runtime session；每次遊戲更新仍須重跑 schema；BSD-3-Clause 需保留 notices |
| A | [Boxofbiscuits97/HD2SDK-CommunityEdition](https://github.com/Boxofbiscuits97/HD2SDK-CommunityEdition) `795e550` | Blender/Stingray 資產讀寫：`utils.slim` 的 DSAR/package 讀取、`utils.hashing` 的 Murmur hash、`stingray/*` 的 mesh／unit／animation／state machine serializer | 只做資產與 cosmetic archive，沒有 native network；根目錄沒有清楚的整體 license，只有內嵌 LZ4 license，重用前需取得授權並保留第三方 notices |
| A | [CowboyBingus/ReinforcementBeaconsFixed](https://github.com/CowboyBingus/ReinforcementBeaconsFixed) `daec655` / v4.5 | `src/archive_loader.lua` 的 build hash gate、`src/spawn_data.lua` 的 guarded snapshot／single-write／rollback、loader API 1 整合；目前 build 25480438 | 明確 `assert(count<=4 and available<=4)`，證明這類 gameplay reader 仍鎖四格；沒有 session admission；無 repository-wide license；不得直接把它改成八格 |
| A | [CowboyBingus/BetterStratagemBounce](https://github.com/CowboyBingus/BetterStratagemBounce) `707dd2a` / v15.3.1 | `src/windows_api.lua` 的 module SHA256、`read`／`write`／`writable_data`／pointer guard；`navigation_patch.lua` 的 snapshot、完整 layout 驗證、partial-failure recovery；目前 build 25480438 | 只改已載入 settings data，不改 executable code、peer 或 roster；無 repository-wide license；不能外推為多人擴容入口 |
| B | [Boxofbiscuits97/HD2-Modding-Wiki](https://github.com/Boxofbiscuits97/HD2-Modding-Wiki) `a94ad10` | `docs/dev/sdk functions/*` 的 archive、manifest、patch、資產工作流和 SDK 使用說明 | 文件站，不含 session/native 實作；根目錄沒有明示 license；內容需以當前遊戲版本再核對 |
| B | [Xaymar/Hellextractor](https://github.com/Xaymar/Hellextractor) `ad4ecf6` | `mode_hash`、`mode_extract`、`hash_db`、`stingray::data_110000F0`、converter registry；可作歷史 archive/hash 解析參考 | 2024-04-13 的舊 extractor，沒有 typelib/session/player；BSD-3-Clause；不能直接套目前 build 的 offsets |

### 與八人實作最相關的具體入口

#### 1. DataLibrary 與 player-count schema

- `Darctor/Helldivers2_RawData/Data/entities/HiveMindComponentData.json` 與 `Data/entity_deltas/entity_deltas_decoded.json` 保存 `player_count_multipliers`；本快照可見的欄位仍是 1～4 項。它適合產生 P6 AI consumer 審計清單，不適合直接寫入 5～8 的數值。
- `Darctor/Helldivers2_RawData/Data/settings/EntityComponentMap.json` 可查 `ShipTeleporterComponentData` 的 component 使用情況。這只能證明資料 component 存在。
- 舊版 `shalzuth/HelldiversData/data/components/EntityNetworkDataArray.json` 的公開定義是 `entities : array<EntityNetworkData>`；`EntityNetworkData.json` 只有 `game_object_id` 和 `settings_hashmap_index`，`NetworkOverrideComponent.json` 只有 `dummy`。這支持「通用 entity array 不是固定四人欄位」的假設，但沒有 native allocator、peer admission 或 client player creation。
- 舊版 `ShipTeleporterComponentData.json` 是 `hashmap` 加 `data : array<ShipTeleporterComponent>`，`ShipTeleporterComponent.json` 的欄位是 `charge_time`、`spawn_time`、`cooldown_time`。這可用於 hot-join schema 對照，不能用來宣稱 teleporter 能建立第 5 名。
- `filediver/hashes/dl_type_names.txt`（本次 checkout 行 475、485、550、871、949、6694～6696）包含 `EntityNetworkDataArray`、`ShipTeleporterComponentData`、`NetworkOverrideComponent`、`ShipTeleporterComponent`、`EntityNetworkData` 以及 `ship_teleporter_deeplink_join`／`network_join` 名稱。它只是 hash/type name catalog。

#### 2. 可借用的 loader、guard 和日誌

- `BingusSharedLoader/src/shared_loader.lua` 暴露 `CowboyBingusModLoader.api == 1`，以 `Application.can_get` 先檢查 resource，再 `pcall(require, name)`；`open_log(filename)` 將診斷寫到 `%LOCALAPPDATA%/CowboyBingus/Helldivers2/Logs`。這適合八人 candidate 的版本拒絕、client/host 日誌和失敗隔離。
- `BingusSharedLoader/src/discover.lua` 的 `discovery.declaration`、`scan`、`enumerate`、`archive_prefix` 可作 addon 宣告與資源 hash 核對；它不提供 peer/session 寫入。
- `BingusSharedLoader/scripts/build_addon.py` 和 `docs/AUTHORING.md` 定義 plaintext 宣告資源、MurmurHash64A、manager manifest 與 v15+ loader 依賴。八人 native bridge 若最後以全客戶端安裝，這可負責安全分發；native DLL 仍需另一個版本化安裝器。
- `BetterStratagemBounce/src/windows_api.lua` 的 `module_hash`、`read`、`write`、`writable_data`、`pointer`、`distance` 是可重用的 fail-closed 讀寫模式；`src/navigation_patch.lua` 顯示完整 snapshot → recheck → write → verify → selective recovery 生命週期。
- `ReinforcementBeaconsFixed/src/spawn_data.lua` 的 `patch.snapshot`、`patch.apply` 與 `archive_loader.lua` 也是同一模式，並且在 build 25480438／EXE 1.8.46015.0 下可重用其 hash gate 和 log 設計。它的四格 assert 必須保留在原 mod，不能搬到八人 sidecar。

#### 3. 可借用的 native/觀測骨架，但不能當成八人橋接

- `CChusky/hd2-tools/hook/hd2_raycast_hook.c` 的 `calc_hook_size`、`build_trampoline`、`install_hook`、`exec_lua` 展示 x64 instruction-aligned hook、trampoline 和隔離 Lua 執行。它沒有 build fingerprint；`RC_BUILD_VER` 是作者自己的 `v10.77`，不是 Steam build。只能作研究對照，不能直接接到 `host_join`／`allocator`。
- `CChusky/hd2-tools/overlay/shm_proto.h` 的 `RC_SHM_MAGIC`、`RC_SHM_VERSION`、`rc_shm_data` 和 bounded arrays 可借用來傳送 diagnostics snapshots。它的資料是 raycast/entity 可視化，不包含 peer id、network index、roster ordinal 或 player handle。
- `CChusky/hd2-tools/hook/watcher.c`／`dll_injector.c` 使用 `OpenProcess`、`WriteProcessMemory`、`VirtualAllocEx`、`CreateRemoteThread`；`watcher.c` 還含 `NtOpenProcess` direct-syscall fallback。這些路徑是高風險 injection／anti-cheat 旁路，不能直接併入本專案的 fail-closed native bridge。
- `Hellextractor/source/mode_extract.cpp`、`mode_hash.cpp`、`hash_db.cpp` 和 `stingray_data.*` 適合把資產／hash 轉成離線輸入；`filediver` 的同類 Go API 更新較新，應優先使用 filediver，Hellextractor 只保留歷史交叉核對。

### 授權與重用規則

1. `filediver` 與 `Hellextractor` 是 BSD-3-Clause，可在保留 copyright、條款和 disclaimer 的前提下重用其原始碼；仍要重新核對當前 build。
2. `shalzuth/HelldiversData` 附 AGPL-3.0。若把其程式碼而非單純研究結果放入交付 Mod，必須先設計對應的源碼提供和衍生作品義務；本專案目前只引用 schema 和欄位名稱，不複製其程式碼。
3. `CChusky/hd2-tools` 是 PolyForm Noncommercial 1.0.0，禁止未授權商業用途；其 injection／anti-cheat 旁路也不適合直接重用。
4. `BingusSharedLoader`、`BetterStratagemBounce`、`ReinforcementBeaconsFixed` 的文件明確寫「No repository-wide license has been selected」。在作者另行授權前，只可引用公開介面、研究結論與文件，不應複製源碼進交付包。
5. `HD2SDK-CommunityEdition` 與 `HD2-Modding-Wiki` 沒有清楚的根目錄授權聲明；SDK 內嵌的 LZ4 授權不等於整個 SDK 可自由重發布。`Darctor/Helldivers2_RawData` 沒有可見 license file，也要按保留所有權利處理。
6. 所有倉庫都涉及 Helldivers 2 的資料、資產或逆向觀測；第三方倉庫的 license 不會授予 Arrowhead／Sony 遊戲內容的權利，也不會解除遊戲服務或 anti-cheat 風險。

### 對本專案的採用決定

- **採用作研究輸入：** `Darctor`、`shalzuth`、`filediver`、`Hellextractor` 的 schema／資產工具；在本地保留 commit 和 metadata，重新生成時綁定精確 build。
- **採用作候選封裝／診斷參考：** `BingusSharedLoader` 的 API 1、discovery、log 和 module guard；`BetterStratagemBounce`／`ReinforcementBeaconsFixed` 的 hash gate、snapshot、rollback 模式。
- **不直接採用作八人 native bridge：** `CChusky/hd2-tools` 的 injection／Lua hook 和所有 raycast-specific layout；`HD2SDK`／Wiki 的資產工作流也不能代替 session admission。
- **未改變驗收標準：** 仍須由 session admission、host/client peer index、confirmed-peer、player creation、roster/component lifetime 串到第五至第八名，再由八個獨立帳號完成同一任務全流程；公開倉庫的 loader、離線 fixture、單機記錄和 entity schema 都不算多人驗收。
