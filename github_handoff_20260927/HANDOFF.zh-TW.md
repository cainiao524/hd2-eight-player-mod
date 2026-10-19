# 歷史交接紀錄

**目前接手入口：[CURRENT.zh-TW.md](CURRENT.zh-TW.md)（2026-10-19）。** 本檔以下依原研究輪次保存；歷史的授權、程序狀態、提交及測試結果不自動代表目前狀態。最新交接文件整理了已用完的一次 v2 採樣授權、尚待授權的 dispatcher 補充範圍，以及八人實測缺口。

原開頭狀態：2026-09-28 已恢復離線工作。
## 2026-10-03 public runtime boundary research

已固定 `SkyeShade/HD2Runtime` master `96ab2d2`、`CowboyBingus/ReinforcementBeaconsFixed` main `daec655` 及 `ModOptionsMenu` main `46d693e`。前兩者能提供版本門控、guarded data transaction、事件／資料修改和逐客戶端安裝模式，但沒有 Party／Session／confirmed-peer／Player Clone admission ABI；ModOptionsMenu 只提供 UI／entry gate。研究結論已保存於 `PUBLIC_CODE_RESEARCH_20261003_RUNTIME_BOUNDARY.*`：Lua／Shared Loader 保留作診斷與資料層輔助，八人突破必須回到 native host/client admission、角色建立、cleanup 与 replication 链。

## 2026-10-03 原生 consumer executor 候選

在 bound candidate 之後新增 `Native/SessionMembers/ep_consumer_executor.h/.cpp` 與可載入的 `ep_consumer_executor.dll`：固定 build `25480438`、入口 `0x1093590`、14-byte fingerprint、270-byte full-replacement stub 和 24-byte registered unwind。安裝器只接受五個非空 callback，先以 `RtlAddFunctionTable` 註冊 unwind，再在入口寫入可回滾的 FF25 absolute detour；移除時驗證 detour 所有權並恢復原始 bytes。`build_consumer_executor_x64.bat` 與 `ep_consumer_executor_test.exe` 在合成 module 上通過 4 人相容、5--8 人 count、count 9 拒絕、缺 callback／入口變更拒絕及 install/remove 恢復。 `ep_consumer_executor_load_test.exe` 另通過 DLL export 與 getter 檢查。

收據為 `eight_player_candidate_20260927/Native/SessionMembers/consumer_executor_receipt_20261003.json`。最新整合提交為 `6b21fc1`；STATE 與收據已同步更新。此 executor 仍是離線 native 安裝器候選：callback resolver、owner lifetime、producer／player creation／cleanup、Party admission 和客戶端 replication 尚未綁定；沒有存取或修改 HD2 程序，`production_executable=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false`。

## 2026-10-03 固定 build native callback binding 候選

`Native/SessionMembers/ep_consumer_native_callbacks.h/.cpp` 依已保存 `0x1093590` body 將四個可由固定 code 直接恢復的 callback 接到版本化 adapter：mode 使用 `game.dll+0x3326340/+0xac4d9` 和 `+0x3326e48/+0x04`，identity 使用 owner `+0xB398`，lookup 使用 `game.dll+0x3326308 → +0xF8 → vtable +0x118` 及 `game.dll+0x2264210` tag，status 使用 `game.dll+0x20BDE78`。PE timestamp／image size 與 Steam build 都 fail-closed；resolver 仍必須由 sidecar owner-lifetime 提供。

`ep_consumer_native_callbacks_test.exe` 通過合成 image、vtable、lookup/status code、固定 identity、版本／映像拒絕與 unbind。這是 ABI binding candidate，bind 本身不呼叫遊戲函式、不安裝 hook；尚無 live callback call、Party admission、player creation 或 client replication 證據，所有正式多人門檻維持 false。

## 2026-10-03 platform-member consumer bound candidate

已把固定 build `0x1093590` consumer 從 sentinel-only template 收束成可重定位的離線候選：`bind_candidate()` 接受呼叫者提供的 code、unwind 和 callback 位址，拒絕未解析 sentinel、非 canonical／未對齊位址、alias、映像與 stub 重疊及相對位移溢出。`test_consumer_bound_execution.py` 以合成 callback 實際跑過 0..8 成員、失敗／缺本機／未 ready／resolver 拒絕、移動後 code 位址、volatile register 破壞與完整 unwind 邊界，4 項通過；既有 consumer、session-member 與 static patch 測試也通過。

同時修正舊 unwind metadata：consumer 序言是 16 bytes；`UWOP_PUSH_NONVOL` 的 register `OpInfo` 現在以正確高半位元組編碼。這讓 native bridge 候選的機器碼驗證可靠，但 callback resolver、owner lifetime、confirmed-peer producer／cleanup 和真實安裝仍未閉合；`installable=false`、`multiplayer_verified=false` 維持不變。最新研究提交為 `6b21fc1`。

## 2026-10-03 game.dll session snapshot contract alignment

已將 `Native/SessionObservation/ep_session_snapshot.h` 從未閉合的 EXE engine-session vtable 假設改為與既有四人實機捕獲相同的 `game.dll` bounded layout：核對固定 `game.dll` PE identity，讀取 context、roster、game-state globals、local/host/session owner、mode、最多八筆 `0x20` stride peer records，以及四筆 documented `0xC0` stride roster records。network index 必須唯一且小於 8；roster slot `4..7` 保持 out-of-contract。Windows wrapper 現在明確取得 `game.dll`，不再把主 EXE 當作映像來源。

`session_snapshot_synthetic_passed`、官方 plugin build、`ep_official_plugin_test.exe` 與 `ep_official_plugin_load_test.exe` 均通過。這只讓官方插件的診斷讀取契約和保存的四人基線一致；沒有新增程序擷取、沒有呼叫 peer／GameSession 方法、沒有第五至第八人證據，`installable=false`、`multiplayer_verified=false` 維持不變。

## 2026-10-03 固定版本容量補丁實機載入

新增 `Native/CapacityPatch` 原生插件候選，固定 `Build 25480438` 與 35 個四人容量／枚舉／加入／狀態更新 site。插件先完成全 site fingerprint preflight，才以單一交易寫入 `8`；任一 site 不符就拒絕，卸載路徑按逆序恢復 bytes。

在 Steam 正常啟動的固定版本實機中，官方 loader 記錄 `loaded`、`applied` 且 `patched=35`；原始收據中的 `GameSessionCApi.num_peers`／`peer_count` 欄位已被 superseded，因為 HD2 的 wrapper/vtable 語義尚未閉合，舊探針不能把該偏移當作可靠 peer getter。實測後已停止遊戲並移除 DLL／marker。

這只閉合容量常數層，沒有證明 Party/PlayFab admission、第五至第八個 confirmed-peer、Player Clone、客戶端 entity replication、死亡增援、重連、撤離或 host migration。`installable=false`、`multiplayer_verified=false` 保持不變。研究與機器收據見 `CAPACITY_PATCH_CANDIDATE_20261003.zh-CN.md`、`live_capacity_patch_runtime_verification_20261003.json`。

## 2026-10-03 公開倉庫研究與官方 C API 邊界捕獲

已固定閱讀三個新增公開倉庫：`MrChengl11/hd2-lua-mod-skill`（`d1811983ab4fec230ede24bdd3d274f77b0b82fd`）、`junze0910/junze-hd2-lua-mod`（`95b2d26ea10ea43281c93123a95d326a289da2ae`）及 `starmatch666-droid/hd2-mod-update-skill`（`2eae30596a0886b4674567f22f549ef03e9b80e4`）。研究結果已寫入 `PUBLIC_CODE_RESEARCH_20261003_NEW_REPOS.*`：可採用離線／唯讀探測、UI 第五槽位寫入風險與 build/hash/table fail-closed 門檻，但三者都沒有 Party → Session → Player Clone 的八人能力證據。

同一固定 build `25480438` 保存了 `Network`／`GameSession` C API table 的 bounded prefix 和候選 engine-session vtable 的靜態前綴。捕獲只讀、重讀相等、沒有呼叫函式、寫記憶體、hook 或注入；wrapper table 與 underlying vtable 分開記錄，不能解讀成 peer admission、player creation 或可安裝 Mod。

最新研究提交為 `e207906`，狀態收據提交為 `e207906`。`installable=false`、`multiplayer_verified=false`、真實第五至第八帳號測試未完成。


## 2026-10-03 最新離線 native bridge hardening

`Native/Bridge` 與 `Native/ClientSidecar` 的候選交易邊界已再收斂：native player creation 先於 bridge sidecar confirm，native confirm 失敗時 adapter 保留補償 identity，由 bridge 的 remove callback 同時清理 native 與兩端 sidecar；cleanup retry 必須帶完整的 peer、resource handle、network index 和 generation，不能只用重用中的 index。跨元件 harness 已實際走過八個 index `0..7`、離隊洞位、generation-safe reconnect、完整雙 registry cleanup 及 owner lease 平衡；adapter destroy 會拒絕仍有 native-confirmed flag 的 teardown。

這些是固定 build `25480438` 的離線 C++／Python 合成驗證，沒有接真實 callback ABI、沒有寫入或注入遊戲程序，`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 仍是正式狀態。原研究提交為 `d465682`，狀態收據提交為 `b0b30ec`；本輪 player-resource、receiver-vector、live layout、ClientSidecar lock hardening、native loader boundary、official plugin directory audit、OfficialPlugin ABI probe、GameSession route audit、C API contract pin、plugin startup boundary audit 與官方插件實機載入觀察的歷史研究提交為 `80e5860`，最新狀態收據提交為 `c4fcaba`。

## 2026-10-03 native player-resource sidecar

新增 `Native/PlayerResource` 八格 C++ sidecar，將固定 build audit 的三張 callback table 固定成 `begin → first → second → third → publish → release` 交易：每個 network index 都保留 generation、owner epoch、peer／resource identity 與 callback lease；第三階段拒絕、callback 順序錯誤和重複 release 都會清除或拒絕 stale record，owner migration 需先 quiesce。`component 239` 僅作為第一張 table 的 roster leaf 契約輸入。

`ep_player_resource_synthetic_passed` 已涵蓋 index `0..7`、佔用第九次拒絕、三階段 callback、失敗回滾與 owner migration；Python report/hash tests 2/2 通過。這是 native 形狀的離線所有權／回滾元件，尚未解析或呼叫 `0x1086460 → 0xFDC140 → 0x581320/0x581780 → 0x540920` 真實 ABI，也沒有 hook、注入、安裝、UI、Party 或多人驗收；`production_executable=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false` 保持不變。

## 2026-10-03 receiver vector ABI adapter

新增 `Native/ReceiverAdapter` 離線候選，固定 `0xBC2D10` callback-vector leaf、selector `168`、table entry `0x214C2E0 + 168*8 → 0xBABA80` 及 descriptor 欄位 `+8/+18/+28/+38/+48`。C++ decoder 只接受 selector `168`，未知 selector／缺欄位 fail-closed；五個值保持 opaque，沒有猜成 peer、resource 或 network index。`ep_receiver_adapter_synthetic_passed` 與 Python report/hash test 通過。

保存的 ABI 仍未閉合 `0x4804FCF4 → selector 168` 的 hash／service registry，故此候選沒有 callback、native hook、遊戲記憶體寫入、安裝或多人功能；`hash_to_selector_proven=false`、`production_executable=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false`。

## 2026-10-03 live client peer layout reread

在固定 build `25480438` 的現行程序 PID `45820` 上，新增兩次 bounded read-only client layout capture。沿保存的 owner→client `+0x162C8`、count `+0xC8`、records `+0xD0`／stride `0x20` 與相鄰 table `+0x150`／stride `0x10` 讀取；兩次 owner、client 位址、四筆 records 和相鄰 table 完全一致。當時 session snapshot 觀察到 host peer `network_index=0`，但此 client object 的 count 為 `0`，四筆 records 與相鄰 table 全零。

這只證明該 menu／one-peer context 的固定 layout 可安全重讀，不把零 count 解讀成 active peer registry，也沒有把它當作第五人或八人證據。工具全程 read-only，沒有呼叫、寫入、hook 或注入；驗證收據中的 `runtime_verified`、`installable`、`multiplayer_verified` 仍為 `false`。

## 2026-10-03 ClientSidecar lock hardening

修正 `Native/ClientSidecar/ep_client_sidecar.cpp` 的同步實作：原候選把 `SRWLOCK` 物件強轉成 `LONG` 自製自旋鎖，現在所有 append／remove／get／reset／validate／destroy 路徑都使用真正的 Windows exclusive SRW lock。ClientSidecar、adapter 與 Bridge/client integration harness 重新建置通過，Python report/hash tests 3/3 通過。

這是隔離 sidecar 的正確同步修補，沒有改變其 native callback、遊戲 hook 或安裝狀態；`production_executable=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false` 保持不變。

## 2026-10-03 fixed-build live preflight reread

在同一固定 build `25480438`、同一 PID `36900` 上保存第二批 bounded read-only reread：

- `live_native_sites_20261003_r2.json`：六個 native site 的 code-image hash 與前一批逐項相同，六個 site 的 reread 均一致。
- `live_session_member_sites_20261003_r2.json`：五個 session/member site 的 hash 與前一批逐項相同，五個 site 的 reread 均一致。
- `live_call_edges_20261003_r2.json`：27 條 direct `E8` edge 集合及唯一 send-side confirmed-peer hash 命中均相同。
- `live_private_registry_20261003_r2.json`：128 MiB bounded private scan 仍為 0 hit。
- `live_preflight_r2_verification_20261003.json`：11/11 固定檢查通過，確認版本／PID／映像與負面 registry 觀察可重播；`resolver_closed=false`、`installable=false`、`multiplayer_verified=false` 保持不變。

這批 reread 只增加固定 build 證據穩定性，沒有提供第五個 peer、player creation、native callback ABI、安裝或多人成功，也沒有呼叫、寫入、hook 或注入遊戲程序。

## 2026-10-03 live session snapshot

新增 [capture_live_session_snapshot_20261003.py](../five_player_feasibility_20260927/tools/capture_live_session_snapshot_20261003.py)，在同一固定 build／PID 以只讀方式觀察已知 network context、peer count、peer index、host/local peer 及四筆 documented roster records。兩次保存的快照顯示 peer count 從 1 到 4，第二次完整讀到四個 peer，index 為 `0..3`；[live_session_snapshot_verification_20261003.json](../five_player_feasibility_20260927/live_session_snapshot_verification_20261003.json) 的 11/11 檢查通過。

這是首次取得真實 session context 的基線證據，確認讀取路徑可用並保留四人原版行為；roster slot `4..7` 不列為有效 inline records。它沒有第五個 peer、player creation、注入、安裝或多人八人成功。初次未帶四槽標註的原始快照仍保留，但不納入 verifier。

後續 bounded 讀取又保存了 [live_session_snapshot_20261003_r4.json](../five_player_feasibility_20260927/live_session_snapshot_20261003_r4.json)：四個 peer、`session_owner` 可讀，`session+0x20` 的 224-byte confirmed-peer window 可完整保存，但只保留 raw bytes/hash，不把欄位解碼成玩家。再一次讀取 [r5](../five_player_feasibility_20260927/live_session_snapshot_20261003_r5.json) 遇到不可讀區域後 fail-closed，沒有把失败當作空表或成功；兩份原始資料均保留。

後續固定 build 程序 PID `22976` 的 [r6](../five_player_feasibility_20260927/live_session_snapshot_20261003_r6.json)／[r7](../five_player_feasibility_20260927/live_session_snapshot_20261003_r7.json) 只補充空 menu 到單一本機 peer 的基線（peer count `0 → 1`、mode `0 → 3`、index `0`）。兩份擷取保持 read-only，沒有第五個 peer、角色建立、注入、安裝或八人成功。

程序退出後對同一 PID 的六個 native site 重讀以 WinError 31 fail-closed；[live_native_sites_20261003_r3.failure.json](../five_player_feasibility_20260927/live_native_sites_20261003_r3.failure.json) 只保存失敗收據，沒有 native bytes 或成功結論。

## 2026-10-03 live preflight continuation

在使用者已授權的範圍內，固定 build `25480438` 的 PID `36900` 完成一批 bounded read-only 證據保存：

- [live_native_sites_20261003.json](../five_player_feasibility_20260927/live_native_sites_20261003.json)：六個 host/client allocator、migration、remove/reset、player-creation fixed sites，全部 first-read/reread 一致。
- [live_session_member_sites_20261003.json](../five_player_feasibility_20260927/live_session_member_sites_20261003.json)：五個 host-join、platform member enumerator/consumer/leaf/state-update sites，全部一致。
- [live_call_edges_20261003.json](../five_player_feasibility_20260927/live_call_edges_20261003.json)：22,271 個 executable pages、27 條 direct `E8` edges；`0x4804FCF4` 只在 send-side `0xBE4982` 命中。
- [live_dispatcher_data_20261003.json](../five_player_feasibility_20260927/live_dispatcher_data_20261003.json)：`0xBDE430` 673-byte live code pin 重讀一致；固定 API/config path 與兩個 image hits 保存，但沒有 heap registry。
- [live_interface_probe_20261003.json](../five_player_feasibility_20260927/live_interface_probe_20261003.json)、[live_signature_scan_20261003.json](../five_player_feasibility_20260927/live_signature_scan_20261003.json) 及 [live_private_registry_20261003_current.json](../five_player_feasibility_20260927/live_private_registry_20261003_current.json)：API/config fixed path、host-join signature、128 MiB private scan 保存；registry bounded scan 0 hit，member-enumerator signature 在該程序狀態 0 hit。
- [live_private_registry_20261003_1g.json](../five_player_feasibility_20260927/live_private_registry_20261003_1g.json)：同一 PID 擴大到 1 GiB committed `MEM_PRIVATE`（1,655 regions／262,144 pages），已知 receiver／insert／member／hash 仍為 0 hit。
- [live_preflight_continuation_verification_20261003.json](../five_player_feasibility_20260927/live_preflight_continuation_verification_20261003.json) 對上述證據執行 22/22 固定檢查；[LIVE_PREFLIGHT_CONTINUATION_20261003.zh-TW.md](../five_player_feasibility_20260927/LIVE_PREFLIGHT_CONTINUATION_20261003.zh-TW.md) 說明限制與下一步。

同一固定 build 的 `MenuScreenLoadout` code-image 也完成獨立 bounded 預檢：[live_loadout_layout_20261003.json](../five_player_feasibility_20260927/live_loadout_layout_20261003.json) 對 `game.dll` 的 226 個 canonical anchors 全部 first-read/reread 一致，總讀取 2,446 bytes；工具與完整收據覆核見 [LIVE_LOADOUT_LAYOUT_PREFLIGHT_20261003.zh-TW.md](../five_player_feasibility_20260927/LIVE_LOADOUT_LAYOUT_PREFLIGHT_20261003.zh-TW.md)。這只核對程式碼映像與檔案指紋，沒有讀 heap、呼叫函式、建立角色、安裝或多人驗收。

同時完成 [selector cleanup xrefs](../five_player_feasibility_20260927/SELECTOR_CLEANUP_XREFS_20261003.zh-TW.md)：registration wrapper `0x1094680` 沒有 direct caller，unregistration `0x1094710` 有 3 個 direct caller，status `0x1094780` 有 3 個；三個 unregistration fragment 都可辨識 `global+0x1f028`。公開同版 Better Lobby 交叉核對把這個欄位及 wrapper 指向 lobby browser/network context，因此不能再把它當成 confirmed-peer/player-admission registry。`selector_registration_xrefs_20261003.json` 只保存 bounded static xrefs，不提供 runtime selector map。



另完成 [PLAYER_CAPACITY_CHAIN_20261003.zh-TW.md](../five_player_feasibility_20260927/PLAYER_CAPACITY_CHAIN_20261003.zh-TW.md) 與其 verifier：`0x10919D1/0x10919DE` owner capacity、`0x10915DA` 初始 metadata、`0x1092E78/0x1092F31` enumerator capacity、`0x1092ECB/0x1092ED0` clamp/store、`0x1093C91/0x1093C96/0x1093D1E` state update、`0x1093A96` recreate add 都被分組核對，11/11 通過。這些是多個獨立四人假設，不能合併成單一常數 patch；`production_patch_ready=false`。

## 2026-10-03 player creation ABI gap

新增 [PLAYER_CREATION_ABI_GAP_AUDIT_20261003.zh-TW.md](../five_player_feasibility_20260927/PLAYER_CREATION_ABI_GAP_AUDIT_20261003.zh-TW.md) 與 43-pin 可重播審計。它把 `0x1086460 → 0xFDC140 → 0x581320/0x581780 → 0x540920` 的建立 ABI、resource record、owner+8 map/flags/count、三組 callback table 及 roster inline pointer 寫入接成一條固定鏈；`index 4..7` 仍在 gate 被導向 fallback，`0x540920` 仍有 `cmp eax,4`。

審計明確保留 `player_resource_reverse_cleanup_proven=false`、`partial_resource_rollback_proven=false`、`owner_migration_and_thread_quiescence_proven=false`、`index_4_to_7_player_creation_proven=false`；測試 1/1 通過，沒有生成 patch、呼叫程序或安裝。

後續固定 capture 審計已閉合玩家 resource 的反向釋放鏈：[PLAYER_RESOURCE_REVERSE_CLEANUP_AUDIT_20261003.zh-TW.md](../five_player_feasibility_20260927/PLAYER_RESOURCE_REVERSE_CLEANUP_AUDIT_20261003.zh-TW.md) 固定 `FDC780 → FDC820 → FDDC80`、handle registry、兩張 component cleanup table 及 owner+8 map 的 last-ordinal compaction。這證明完整 cleanup 的資料契約，但 partial callback rollback、re-entry idempotence、owner quiescence 及 index `4..7` runtime record 仍未證明；報告仍 fail-closed，沒有生成 patch。

## 2026-10-03 MenuScreenLoadout 八槽布局審計

新增 [LOADOUT_LAYOUT_RELOCATION_AUDIT_20261003.zh-TW.md](../five_player_feasibility_20260927/LOADOUT_LAYOUT_RELOCATION_AUDIT_20261003.zh-TW.md) 與 26/26 固定檢查。`MenuScreenLoadout` 的四筆 `0x9F0` network-index 記錄後緊接兩張四項 map；第 5 筆會覆蓋 inverse map／flags。四個 `0x1EE18` widget 若直接延伸到八項，結束於 `0x14AB38`，會與原下一物件 `0xCF2D8` 重疊 `0x7B860` bytes；內聯配置至少要到 `0x2EF230`，或改用完整 sidecar。

這補上 P6 的 UI／loadout 固定四槽證據，但尚未綁定 reader、writer、transition、destructor、callback 或重連 ABI；`production_patch_ready=false`、`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 保持不變。

新增 [LOADOUT_LIFECYCLE_ABI_20261003.zh-TW.md](../five_player_feasibility_20260927/LOADOUT_LIFECYCLE_ABI_20261003.zh-TW.md) 與 12/12 固定檢查：外層 entry rebuild、screen／widget constructor、兩條 release、transition callbacks 及 14 個 runtime 四槽 guards 均已配對。這仍只支持版本化 sidecar 的設計，未閉合 native object allocator、package unload、完整 reader/writer 或實機畫面同步。

已將這個下一步實作成 [LOADOUT_SIDECAR_CONTRACT_20261003.zh-TW.md](../five_player_feasibility_20260927/LOADOUT_SIDECAR_CONTRACT_20261003.zh-TW.md)：八個 stable network slots、獨立 UI slot／widget token、generation-safe hole、pending／confirmed／releasing 生命週期與 forward／inverse map invariant 均有 5 項合成測試；新增嚴格型別 identity guard，並以 `cancel_pending` 完成被拒絕的 widget／資源建構回滾。它仍是離線 sidecar；沒有 native callback、UI package、遊戲程序或多人驗收，所有 production/runtime/install/multiplayer flags 仍為 false。

另修正 ClientSidecar callback adapter 的安全邊界：native confirm/create/remove 及 owner retain/release callback 現在全部為必要項；所有 network index（含 0–3）都必須經過 native create，confirm 失敗會保留 identity 供 Native Bridge 的 remove compensation 同步清理，remove 失敗會保留記錄供重試。合成測試重新通過，這仍是隔離 sidecar，沒有真實 callback ABI、遊戲 patch 或多人成功。

## 2026-10-03 player-resource rollback 與 peer lifecycle sidecar 契約

新增 [RESOURCE_ROLLBACK_QUIESCENCE_CONTRACT_20261003.zh-TW.md](../five_player_feasibility_20260927/RESOURCE_ROLLBACK_QUIESCENCE_CONTRACT_20261003.zh-TW.md)：以固定 player-creation／reverse-cleanup evidence 為輸入，離線模型覆蓋三張 ABI callback table、第一張 table 內的 component-239 roster insertion、第三階段失敗的反向回滾、release/re-entry tombstone 冪等、generation／owner epoch stale 防護、callback lease 靜默及 owner migration；9 項測試通過。這只收斂後續 native adapter 必須遵守的契約，沒有產生 native patch。
另新增 `player_resource_callback_abi_binding_20261003.json` 與 verifier：逐項核對三張 callback table、component `239` roster leaf、`0x581320/0x581780` dispatch ABI、`0xFDC820/0xFDDC80/0x172F8A0` 反向清理邊界；9/9 靜態檢查通過。它只證明離線契約與保存的固定 build 報告一致，沒有證明第五至第八位玩家能到達 runtime 建立路徑。

新增 [PEER_LIFECYCLE_SIDECAR_CONTRACT_20261003.zh-TW.md](../five_player_feasibility_20260927/PEER_LIFECYCLE_SIDECAR_CONTRACT_20261003.zh-TW.md)：分離 network index、member／peer identity、resource handle、callback lease 與 host owner，覆蓋 partial confirmed-peer rollback、pending cancel、離隊冪等、重連 generation、callback quiescence 及 host migration prepare／commit／abort；8 項測試通過。合成報告的 native owner、runtime、installable 與 multiplayer flags 仍全部為 false。

## 2026-10-03 staging gate 接入離線審計

`eight_player_candidate_20260927/Package/stage_package.py` 現在在 staging 判定前讀取並驗證上述五份固定 build 審計：player-creation ABI 43 個 pins、MenuScreenLoadout relocation 26/26、player-resource reverse cleanup、rollback/quiescence sidecar 與 peer lifecycle sidecar；缺檔、schema、build、固定 pins、生命週期檢查或 fail-closed flags 不符都會阻擋 staging。這些報告仍只是證據閘門，不能把 `production_patch_ready=false` 轉成可安裝。

針對固定遊戲目錄重新產生的 [diagnostics.json](../eight_player_candidate_20260927/Package/diagnostics.json) 顯示五份 offline audit `valid=true`，但 native plan `executable=false` 且 native payload 缺失，因此整體仍 `activation_allowed=false`；沒有寫入遊戲目錄、安裝、注入或多人驗收。Package 測試目前 10 項通過。

上述資料均為 `read_only=true`、沒有函式呼叫、寫入、hook、注入、安裝或多人驗收；`resolver_closed=false`、`installable=false`、`multiplayer_verified=false` 保持不變。下一個實作門檻回到 host/client peer admission → confirmed-peer → player creation 的真實第五人流程，selector registry 只能在取得 runtime 證據後再評估。

2026-10-02使用者明確授權第四次限定擷取、遊戲程序存取、載入／注入、安裝修改與後續真實測試；後續只在固定 build、可回滾 staging 和 fail-closed gate 下使用這份授權。

使用者已明確要求接續完整八帳號同任務全流程目標。6054F0 候選已完成接續oracle審查、契約、manifest、五份全域文件及本機交付收據更新，正式離線版本為 **0.14.0-offline**。原source、測試及凍結報告保持相同；只重跑6054F0五組／42次，執行紀錄完全一致。共同bundle16個roster函式／62區域，v0.14候選交付bundle為149組／4,314次套件執行或觀察；STATE續接審計總數另記為152組。

已按工作清單完成下一個[1277920有限調查](../five_player_feasibility_20260927/roster_mask_reader_findings.zh-TW.md)：確認primary+24h與property+Ch兩處需改接，24次原前綴觀察未證明mask拒絕玩家；固定 build 的離線 reader 候選與 6 項隔離驗證已保存。完整八人目標保持未完成。

2026-10-02已完成[公開程式碼與研究核對](../five_player_feasibility_20260927/PUBLIC_CODE_RESEARCH_20261002.zh-TW.md)：沒有找到已驗證的HD2五至八人同任務成品 Mod；公開 Better Lobby 同版資料仍以四筆 peer／roster 為界，FileDiver 只提供型別名稱，OTL 的 Patrol consumer 仍是1–4人。後續按第五人 session admission → peer/index → confirmed-peer → player creation 鏈推進。

第四次授權擷取已完成：[spawn_callee_live_20261002_4.json](../five_player_feasibility_20260927/spawn_callee_live_20261002_4.json) 與 [live_native_session_capture_20261002.json](../five_player_feasibility_20260927/live_native_session_capture_20261002.json) 均保留原始證據；後者包含 10 個 game native roots 與 Party 間接槽。另保存了一次程序結束造成的重新讀取失敗審計，沒有把失敗嘗試當成成功擷取。

第五次授權擷取已完成：[live_native_sites_20261002_5.json](../five_player_feasibility_20260927/live_native_sites_20261002_5.json) 只讀核對六個固定 game.dll site，沒有寫入、hook、注入或多人測試。另完成 [CChusky hook 靜態評估](../five_player_feasibility_20260927/CCHUSKY_HD2_TOOLS_HOOK_ANALYSIS_20261002.zh-TW.md)；該工具沒有 Session／Party／peer／roster／player creation production bridge。

同次授權另保存 [interface_probe_live_20261002.json](../five_player_feasibility_20260927/interface_probe_live_20261002.json)：只讀取得固定 API/config root 與兩個間接函式前綴，欄位重讀一致；沒有呼叫函式、寫入、hook 或注入，結果仍不代表服務加入或多人成功。

其分析見 [INTERFACE_PROBE_LIVE_ANALYSIS_20261002.zh-TW.md](../five_player_feasibility_20260927/INTERFACE_PROBE_LIVE_ANALYSIS_20261002.zh-TW.md)：`API root+0xf8/+0xa0` 的 live target 會把第一個整數參數寫入新物件 `+0x20`；結合既有建立路徑的靜態證據，這是平台物件建立資料流可能已有八的正面線索，但尚不能命名為後端 max member，也沒有接通列舉、peer 或 player creation。

更早保存的 `engine_f8_request_evidence.json` 已把同一固定版本呼叫形狀高信心對照到 `PartyManager::CreateNewNetwork` 的 `PartyNetworkConfiguration`，觀察請求為 `(8, 8, 1, 1, 1, 0xF)`。這表示平台層可能已收到八使用者／裝置的請求；服務端接受、host/client 名冊與可玩角色仍未驗證，不能把它當成八人成功。

另新增 [Host Join Runtime Probe](../eight_player_candidate_20260927/Native/RuntimeProbe/README.zh-TW.md)：只保存外部觀測器複製後傳入的 `0x108BC70` 入口 frame，固定 32 筆 ring、最多 16 個 stack word，並有 build/site、停止、滿載和 profile fail-closed。合成 harness 通過，但沒有 game RVA installer，也未注入或呼叫遊戲函式。

另外新增 [八帳號 live acceptance verifier](../eight_player_candidate_20260927/Integration/verify_multiplayer_acceptance.py)：驗收輸入必須是八個獨立 account/client、同一 mission/session/build、index `0..7`、唯一 peer/resource/entity/roster，以及完整死亡、增援、離隊、重連、撤離、結算和 host migration 事件；少於八份、重複識別、非 live input 或缺欄位都會拒絕。

已完成 [native Peer Admission Adapter](../five_player_feasibility_20260927/NATIVE_PEER_ADMISSION_ADAPTER.zh-TW.md) 與 [live build preflight](../eight_player_candidate_20260927/Integration/LIVE_BUILD_PREFLIGHT.zh-TW.md)。六份 build 檔案核對成功、程序停止、native plan schema 有效，但 plan 仍為 `executable=false`；因此未安裝、未注入，也未宣稱多人成功。Integration 測試目前 10/10 通過。

同輪已建立 [x64 hook scaffold](../eight_player_candidate_20260927/Native/HookPrototype/README.zh-TW.md)：合成目標 2/2 通過，涵蓋可回滾 trampoline、Windows unwind registration、RIP-relative／rel32 指令重定位與 host-join prologue 核對。`0x108C18F` capacity gate 的中段 bridge 另見 [midgate plan](../five_player_feasibility_20260927/midgate_bridge_plan_20261002.json)；它仍是設計與測試證據，沒有遊戲安裝出口，native plan 維持 `executable=false`。

另完成 [native sidecar table](../eight_player_candidate_20260927/Native/Sidecar/README.zh-TW.md)：獨立 x64 DLL 提供八個 stable slot、pending／confirmed、generation-safe hole／reconnect、重複 identity／resource 拒絕與 invariant 驗證；合成 harness 與 report test 通過。它尚未接到 Session／Party、confirmed-peer 或 player creation callsite，所以不能作為安裝 payload。

本輪再完成 [Native Bridge orchestration candidate](../eight_player_candidate_20260927/Native/Bridge/README.zh-TW.md)：把 sidecar 接到 build/site/callback preflight、confirmed-peer／player-creation callback 契約、admission rollback、departure cleanup 和 generation-safe reconnect；八人合成 harness 通過並拒絕第九人，跨元件 harness 另通過八個 index 的離隊／重連／清理。這仍是 callback ABI 的隔離候選，沒有真實 game.dll patch 或注入，production plan 維持 `executable=false`。

另完成 [native peer admission bridge boundary review](../five_player_feasibility_20260927/NATIVE_PEER_ADMISSION_BRIDGE_BOUNDARY_20261002.zh-TW.md)：固定 `0x108C18F` capacity、`0x108C3D8` allocator、confirmed-peer sender/receiver、client append、player gate 與 cleanup/migration 的 4/4 靜態檢查通過；Bridge 合成層新增 owner retain/release lease，確保 callback transaction 在 host migration 或清理期間不使用失效 owner。這些仍是 fail-closed 契約，沒有 production ABI 或多人驗收。

本輪已實作離線[八人容量與接納契約](../five_player_feasibility_20260927/EIGHT_PLAYER_CAPACITY_CONTRACT.zh-TW.md)、[peer admission adapter](../five_player_feasibility_20260927/PEER_ADMISSION_ADAPTER.zh-TW.md)、顯式 admission observation schema、build/profile fail-closed gate，以及 `1277920` roster mask reader 候選。Python 契約與觀測測試共13項、adapter 5項通過，reader Unicorn/Capstone 6項通過；所有產物仍 `installable=false`、`multiplayer_verified=false`。

目前來源以[STATE.json](STATE.json)、[候選契約](../eight_player_candidate_20260927/NATIVE_ROSTER_ARRIVAL.zh-TW.md)及[交付收據](../eight_player_candidate_20260927/verification/delivery_checks.json)為準。第四次擷取已獲使用者明確授權並完成；目前尚未宣稱五至八帳號任務驗收完成。

以下保留2026-09-27原交接內容作歷史紀錄，其暫停／v0.13／缺少審查的敘述已由上方更新取代。原狀態另存[STATE.at_pause.json](STATE.at_pause.json)，原v0.13收據另存[delivery_checks_v0.13.json](../eight_player_candidate_20260927/verification/delivery_checks_v0.13.json)。上傳收據及快照清單仍描述原GitHub資料提交；本句保留暫停當時的狀態，後續 live preflight、玩家資源清理、loadout lifecycle 與 sidecar 契約變更已由 `b0b86a0` 推送至 main，狀態收據再由後續提交更新。

---

# GitHub 接續交接：依使用者要求停止

## 先讀這兩份檔案

1. [完整目標](GOAL_OBJECTIVE.zh-TW.md)：原目標逐byte副本，沒有縮小八人驗收範圍。
2. [暫停時檔案指紋與待辦](STATE.json)：辨認已交付版本和尚未收尾的新候選。

使用者已要求暫停，準備建立新GitHub倉庫並上傳相關工作，之後另行交接。所有三個研究／測試分支均已中斷。目標工具查詢回傳 null；不要自動重建或繼續目標，須等使用者明確恢復。此交接文件的保存不是恢復研發。

## 完整目的與實際狀態

完成八名真人、八個獨立帳號在同一任務合作的可安裝HD2 Mod，包含原始碼、相容版本、建置／安裝／移除、錯誤診斷與完整實測紀錄。第五人只是中途門檻。

目前仍沒有可安裝、已驗證可玩的五人或八人Mod。現有產物是版本固定的離線原生候選、合成記憶體指令測試及研究證據；不可把模擬八筆資料、綠色測試或loader載入當作多人成功。

## 最後完成的正式交付：v0.13

- `eight_player_candidate_20260927/candidate-manifest.json` 仍為 `0.13.0-offline`。
- `verification/delivery_checks.json` 仍是v0.13收据；15個候選來源檔、14份測試報告、144組／4,272次套件執行或觀察。
- v0.13共同bundle有15個roster函式與獨立player_count計畫，59個已知區域。
- 4,272包含原版基準、拒絕、26次context前綴觀察及預期原版反例，不能稱為候選成功次數。
- 五份全域文件在暫停時尚未升到v0.14；它們列6054F0為下一切點，應與下述未發布實作一起閱讀。

## 暫停時的新實作：6054F0狀態更新，尚未發布v0.14

工作檔名使用`arrival`，但這個函式沒有新增map項目或增加T/D/P，沒有證明它就是完整加入／append流程。

已保存：

- `Native/roster_arrival.py`：完整1111-byte原body產生1917-byte候選；19個陣列／衍生基址改接共同B，41個局部分支、23個RIP參照、4個直接及4個間接calls保留。
- 入口guard檢查綁定、target／caller-state非null、數量、map key／ordinal及實體pointer；保留原frame、cookie、暫存器與重要條件旗標。
- 原network index 0..3走四列palette，>=4保留原白色fallback，沒有把四列表直接擴讀至八列。
- 原三處通知繼續傳當時D，沒有套用departure的預測公式。
- 新共同sample含16個roster函式、原player_count計畫及62個已知區域；嵌入v0.13產物相同。主代理已經由CLI重建，逐byte一致。
- `tests/test_native_roster_arrival.py`及報告已凍結：5組／42次頂層執行全部通過，分為原版完整4、候選完整21、入口拒絕17。內層真FD9AF0共25次，另列不加總。
- 全19位點靜態核對，其中17個有效輸入可達位點有動態斷言；6056C8／6056D6的invalid-ordinal分支被入口guard擋住，只有靜態核對。
- `verification/native_roster_arrival_review.zh-TW.md`獨立source審查已落檔，未發現局部阻塞缺陷。
- `five_player_feasibility_20260927/roster_arrival_native_*`保存replay、兩份逐byte一致evidence、findings及prerequisites。

尚未完成的收尾：

1. 獨立oracle審查代理已回報有限核對未見缺陷，但被暫停時**尚未寫出**`verification/native_roster_arrival_test_review.zh-TW.md`。口頭回報不能當作已交付審查文件，恢復後需據實檢查並補存。
2. `NATIVE_ROSTER_ARRIVAL.zh-TW.md`是已保存的契約／CLI草稿，測試段尚未完成正式數字與審查連結。
3. Manifest、README、REPORT、WORKLIST、PLAN、VERIFICATION與delivery receipt尚未納入新候選。不能聲稱v0.14正式交付完成。
4. 完成上述核對後，本輪套件總數應為149組／4,314次；目前正式v0.13仍是144／4,272。先查實檔與報告，再更新總數。

恢復後先收尾這份已有實作，避免從頭重做6054F0研究或重跑未改的舊套件。候選以外的下一有限reader可考慮既有清單的`1277920..1277F7B`（network-index／32-bit mask流程）；尚未開始該研究。

## 授權與確定缺口

前三次各一次的本機唯讀擷取均已使用。第四次EXE+1AE380限定擷取未收到明確答覆，`spawn_callee_live_20260927_1.json`仍不存在。不要把第三次同意當成新授權，也不要重問既有待答覆問題。沒有程序查詢、新capture、注入、遊戲修改或安裝授權的延伸。

目前尚不能安排五位玩家／五個帳號。平台加入、額外原生角色、所有客戶端同步、死亡／增援／重連／撤離／結算，以及八人負載仍缺真人驗收。Sidecar配置／發布／清理、完整reader集合、真實資源、callback期間狀態穩定、reject handlers、hook、Windows unwind及封裝也仍未完成。

## 移到新倉庫時的資料位置

目前workspace：`E:\File\Codes\0\26.10.1\HD2`。核心相關目錄至少包括：

- `eight_player_candidate_20260927`：候選、測試、合成產物與交付紀錄。
- `five_player_feasibility_20260927`：研究、固定證據、重播程式及全域計畫。
- `research_handoff_20260927`：保存capture reader等重播依賴。
- 本目錄：完整目標副本與暫停交接。

各研究可能引用其他既有工作目錄；此清單不是可刪除其他資料的白名單。保留使用者原有武器／治療手槍等無關工作。

原目標位於workspace外的Codex附件，已複製到本目錄。另有重播所需的原始capture仍在workspace外：

`C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438`

該capture的report/data SHA分別為`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`與`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。此次GitHub移交會將這兩份既有檔案逐byte複製至`evidence/existing-code-evidence-25480438/`；新環境依[SETUP](SETUP.zh-TW.md)使用倉庫內路徑。原始檔保持在原位置，沒有新增擷取。已保存的evidence內也有本輪完整函式及指定readonly bytes。

目前測試使用`C:\Program Files\Python312\python.exe`（Python3.12.10），Unicorn2.1.4／Capstone5.0.7位於候選目錄`.native-test-deps`。這些本機絕對路徑不是新機器已配置的證據；恢復時先依現有需求檔與可用runtime處理環境。

依使用者後續要求，已建立私人GitHub倉庫：https://github.com/cainiao524/hd2-eight-player-mod ，並準備保存八人研究與必要依賴。資料推送完成後的結果與資料提交編號會記錄於`UPLOAD_STATUS.json`，`STATE.json`的上傳欄位亦會更新。快照清單對應資料提交，狀態收據為後續提交；詳見[SETUP](SETUP.zh-TW.md)。研發保持停止，待使用者明確恢復後再接續。

## 可貼給新對話的接續指示

> 先讀`github_handoff_20260927/GOAL_OBJECTIVE.zh-TW.md`、`HANDOFF.zh-TW.md`與`STATE.json`，以實際檔案為準。完整目標仍是八帳號同任務全流程的可安裝Mod。先核對並收尾已實作但尚未正式發布的6054F0狀態更新候選，再按工作清單推進。前三次擷取授權已用完，第四次尚待答覆；不要自行存取遊戲程序或把離線通過當作多人成功。保留所有無關工作。
## 2026-10-02 native candidate continuation

本次已完成固定 build 25480438 的下一批可審核候選，但仍未安裝或宣稱多人完成：

- `Native/Bridge` 加入同步 operation guard、owner lease、失敗 cleanup retry、離隊/重連回滾與 destroy fail-closed；合成 harness 通過。
- `Native/MidGate` 產生 `0x108C18F` capacity 和 `0x108C3D8` allocator 的精確 machine-code template、continuation、可回滾 patch record 與 x64 `UNWIND_INFO`；四項靜態測試通過。
- `Native/HookPrototype` 修正 runtime function range 與 version-1 unwind metadata；synthetic harness 和 Python tests 通過。
- `Native/ClientSidecar` 保存 32 個四槽 anchor 的 exact bytes/SHA，加入 0..7 stable slot、hole/generation cleanup 及 fail-closed callback adapter；合成測試通過。
- `Native/SessionMembers` 覆蓋 `0x1092E60–0x1092F63` 平台成員列舉 body，將兩條路徑改為八槽 sidecar 候選；原版與候選 bytes 的 Unicorn 4/4 測試通過。

上述內容仍是 static/synthetic candidate。`executable=false`、`mod_installed=false`、`multiplayer_verified=false` 保持不變。真實 callback/dispatcher、所有四槽 reader/writer、Party service acceptance、thread quiescence、可回滾安裝，以及五至八帳號同任務的死亡/增援/離隊/重連/撤離/結算驗收仍未完成。不要把這些候選 DLL 或 template 直接放入遊戲目錄。

追加一份只讀程序狀態證據：[game_signature_scan_live_20261002.json](../five_player_feasibility_20260927/game_signature_scan_live_20261002.json)。在 PID 42592 的前 256 MiB committed executable image regions 掃描固定 host-join 與 platform-member-enumerator prefix，沒有找到 exact hit；這只能說明目前程序狀態沒有暴露這兩個 capture prefix，不能推論函式不存在，也沒有呼叫或寫入程序。

後續恢復了 `0x1093590` platform-member consumer 的 335-byte 固定 build body 與 ABI：[platform_member_consumer_abi_20261002.json](../eight_player_candidate_20260927/Native/SessionMembers/platform_member_consumer_abi_20261002.json)。`RCX=owner`、`owner+0x1B58` 成員 ID、`owner+0x1BB0` count、ready/status/helper 與兩個 caller 已保存；隔離模型 7 項測試通過，但真實 resolver、hook 和 sidecar owner lifetime 仍未接線。

其後新增 [platform_member_consumer_patch_candidate_20261002.json](../eight_player_candidate_20260927/Native/SessionMembers/platform_member_consumer_patch_candidate_20261002.json)：14-byte absolute detour、270-byte full-replacement stub、非易失寄存器保存與 x64 unwind metadata 均通過 2 項靜態測試。callback 地址仍是 template sentinel，production gate 保持 false。

另完成[公開 runtime / loader bridge 核對](../five_player_feasibility_20260927/PUBLIC_RUNTIME_BRIDGE_ANALYSIS_20261002.zh-TW.md)：同版 HD2Runtime v0.28.1 與 Better Lobby v1.1 都只有四人讀取或觀測能力，沒有可移植的 confirmed-peer/player-creation/cleanup bridge；native plan 維持 `executable=false`。

最後補齊相鄰 leaf reader `0x10936E0`：保存完整 118-byte body，並生成 `platform_member_leaf_reader_patch_candidate_20261002.json` 的 14-byte template detour。靜態測試與 verifier 為 2/2，stub 89 bytes；resolver、mode callback、sidecar result lifetime 以及 `0x10937A0` 的所有 count-driven reader/writer 仍未接入真實 dispatcher，因此仍不可安裝。相關收據為 `platform_member_leaf_reader_patch_verification_20261002.json`。

`adjacent_member_boundaries_20261002.json` 和 `ADJACENT_MEMBER_BOUNDARIES_20261002.zh-TW.md` 進一步保存 87 個目前 capture pins。`0x10937A0..0x10945D8` 是 3640-byte state update routine，包含分散的 member/count/control writes、兩組 `capacity=4` gate 及多個 caller side effect；目前以 `blocked_safe_patch` 收尾，沒有生成會繞過整個 state machine 的入口 patch。

重新啟動固定 build 後，PID `38588` 的只讀 live image 預檢成功：`game.dll+0x108BC70` host-join signature 命中，`0x1092E60`、`0x1093590`、`0x10936E0` 的保存 body 逐段重讀一致，與離線 evidence SHA 完全相同；詳見 `live_session_member_sites_20261002_r2.json` 和 `live_session_member_sites_verification_20261002_r2.json`。這只證明目前 native image 與固定 build 對齊，沒有呼叫函式或修改程序。

新增 [LIVE_NATIVE_RESOLVER_ANALYSIS_20261002.zh-TW.md](../five_player_feasibility_20260927/LIVE_NATIVE_RESOLVER_ANALYSIS_20261002.zh-TW.md)：在同一 PID 的 22,271 個 executable pages 中重讀 27 個 direct `E8` edges，確認 `0x1092F4E`、`0x10944FC` 呼叫 consumer，`0x108F078`、`0x134E44A`、`0x13F788A` 呼叫 state update，並唯一定位 confirmed-peer send hash `0x4804FCF4` 於 `game.dll+0xBE4982`。仍未找到 writable receive dispatcher registry、真实 resolver、owner cleanup ABI 或 4..7 player creation callback，因此沒有生成可安裝 patch。

state update 的完整 819 指令、71 個 owner field sites 與 14 個 immediate-4 sites 已保存於 `platform_member_state_update_disasm_20261002.json`；它明確要求 owner-keyed sidecar、所有 reader/writer redirect、間接 callback 和 exception/cleanup ABI，不能安全地只把常數 4 改成 8。

公開 CChusky hook 核對也已補上可重跑 receipt：其能力仍限於 entity/raycast 觀察和 DLL 注入器，沒有 confirmed-peer/player-creation/cleanup bridge，判定維持 `bridge=false`。

### 2026-10-02 confirmed-peer admission ABI continuation

使用者授權的 PID `38588` 只讀捕獲了四個固定 native 區段，保存於 `five_player_feasibility_20260927/native_admission_confirmed_peer_live_20261002_r3.json`；沒有呼叫、寫入、注入或 hook。Host confirmed-peer sender 的完整 body 已從 `game.dll+0x108C760..0x108CD7C` 解碼：1564 bytes、body SHA-256 `633d40a8f3815a1451064a62260f6657524ff5159d5b0c48e803ee883a150f4d`。ABI 與固定邊界收錄在 `eight_player_candidate_20260927/Native/SessionMembers/confirmed_peer_admission_live_abi_20261002.json` 和 `CONFIRMED_PEER_ADMISSION_20261002.zh-TW.md`。

目前已確認：`session+0x20` stride `0x38` 的 peer search 上限 4、ordinal `1..4` gate、`session+0x40` stride `0x38` 的四筆 send loop、`root+0x16418` stride `0x10` 的四筆 side-event loop；另外 `0x108C18F` capacity gate 和 `0x108C3D8` index allocator 仍各自含四槽邊界，`0xB90B20` 是另一條 client confirmed-peer insert/cleanup 路徑。只修改 sender 常數會越過現有 table 或把第五筆送到四槽 receiver，因此 `confirmed_peer_admission_sidecar_adapter.py` 以 owner-keyed sidecar、8 筆 storage、serializer/receiver、migration/departure cleanup、unwind proof 為必要條件並 fail-closed。

靜態 verifier 與 adapter 測試共 10 項通過；收據為 `confirmed_peer_admission_live_verification_20261002.json`。所有產物仍 `installable=false`、`multiplayer_verified=false`，沒有生成或安裝 sender patch。

## 2026-10-02 admission / state-machine continuation

同一固定 build 的 PID `38588` 又完成限定只讀驗證，保存 [LIVE_ADMISSION_SITE_ANALYSIS_20261002.zh-TW.md](../five_player_feasibility_20260927/LIVE_ADMISSION_SITE_ANALYSIS_20261002.zh-TW.md) 與 `native_admission_sites_live_20261002_r2.json`：`0x108C18F` host capacity、`0x108C3D8` allocator、`0x108C760` confirmed-peer sender、`0xB90B20` client insert、`0x1086460` player creation gate 的 live code 與既有固定 build 對齊。觀察到 host/sender 的明確四槽迴圈，以及 player creation 對 index `>=4` 的拒絕；`client insert` 雖有部分 `cmp 8` 查找，inline record 後的欄位已被使用，不能直接追加第五筆。

新增 [CONFIRMED_PEER_ADMISSION_20261002.zh-TW.md](../eight_player_candidate_20260927/Native/SessionMembers/CONFIRMED_PEER_ADMISSION_20261002.zh-TW.md) 與 `confirmed_peer_admission_live_abi_20261002.json`：`0x108C760..0x108CD7C` 的 1564-byte sender body live SHA 為 `633d40a8f3815a1451064a62260f6657524ff5159d5b0c48e803ee883a150f4d`；確認 host/session、peer、transport context、aux ABI 與四槽 table/side-event loops。sender-only、缺 serializer/receiver/storage/migration/cleanup/unwind 的方案由 sidecar adapter fail-closed 拒絕，測試與 verifier 通過，仍 `installable=false`。

`0x10937A0` 的 819 指令 state-update disassembly 已補上四個 coherent capacity sites 及全部 required redirects；`platform_member_state_update_sidecar_adapter.py` 只允許離線八 ID model，任何 partial native plan 或 installable claim 均拒絕。state update、confirmed-peer sidecar 與 live ABI 合計 10 項測試通過。

live resolver 仍未閉合：`live_dispatcher_data_20261002_3.json` 新增 `0xBDE430` generic send dispatcher 673-byte code pin，重讀一致；`live_dispatcher_data_20261002_2.json` 的 image scan 仍只找到 send hash `0x4804FCF4` 和 receiver pointer `0xBABA80`，private scan 128 MiB/295 regions 為 0 hit。這些是 send-side/code identity 證據，不是 hash-to-receive callback registry；沒有呼叫、寫入、hook、注入、安裝或多人驗收。

live-vs-disk 對照又保存於 `live_dispatcher_data_20261002_4.json`：`0xBDE430` live 673-byte body 兩次讀取 SHA 一致；與 PE raw section 同 RVA 不同，僅作 relocation/load 差異診斷，禁止把 raw bytes 當 patch。這仍沒有閉合 receive registry 或 resolver，也沒有任何注入、寫入、安裝或多人驗收。

### 2026-10-02 confirmed-peer 外部鏈 exact evidence

新增 `eight_player_candidate_20260927/Native/SessionMembers/confirmed_peer_external_chain_20261002.json` 與 `CONFIRMED_PEER_EXTERNAL_CHAIN_20261002.zh-TW.md`，把固定 build `25480438` 的 host capacity `0x108C18F`、host index allocator `0x108C3D8`、confirmed-peer sender `0x108C760`、client append `0xB90B20`、player creation gate `0x1086460` 和四條 cleanup/migration 路徑收斂成機器可核對的外部 ABI 鏈。其只讀驗證為 5 sites、2/2 tests，`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。`0xB90B20` 第五筆會寫入 `client+0x150` 鄰接 live 欄位；因此 sender-only 或單改容量仍被 fail-closed。

`live_dispatcher_data_20261002_6.json` 又讀取固定 config root `game.dll+0x3326340` 的 root page 及 64 KiB/16 pages 限定範圍；目標函式與 event hash pattern 0 命中。這只收窄 writable registry 未出現在已知 config path 的結論，沒有把 config root 當作 receive resolver，也沒有呼叫、寫入或安裝。

## 2026-10-03 receiver binding boundary

新增 [RECEIVER_BINDING_BOUNDARY_20261002.zh-TW.md](../five_player_feasibility_20260927/RECEIVER_BINDING_BOUNDARY_20261002.zh-TW.md) 與 machine verifier：固定 capture 已核對 `0xBE4910 → 0x4804FCF4 → 0xBABA80 → 0xB90B20`，以及第五參數寫入 confirmed-peer record `+0x14`；592-entry code-pointer run 的 entry 168 指向 `0xBABA80`。這只閉合靜態資料鏈，沒有 receiver-side writable hash registry、receive ABI、owner storage relocation/cleanup 或 unwind 證據，production gate 保持 `blocked_receiver_registry_unresolved`、`installable=false`、`multiplayer_verified=false`。

## 2026-10-03 player creation chain audit

新增 [PLAYER_CREATION_CHAIN_AUDIT_20261002.zh-TW.md](../five_player_feasibility_20260927/PLAYER_CREATION_CHAIN_AUDIT_20261002.zh-TW.md) 與可重播 JSON：固定 `0x1086460` gate 明確拒絕 index `>=4`；index `0..3` 才進 dummy/player resource、`0xFDC140` component dispatch 與 `0x608B60` roster 路徑，`4..7` 進 fallback ring 而沒有 player-resource dispatch。另核對 `0xB9014B`、`0x13951A9`、session update 四站及七個 player component 的四人護欄。測試 4/4 通過，但這是靜態鏈審計，未生成 executable patch，`runtime_verified=false`、`multiplayer_verified=false`。

Player-chain 審計又補進三個 client layout 固定四人位點：`0x1087122` adjacent lookup bound，以及 `0x10849F7..0x1084A28`、`0x1087260..0x1087298` 的四筆 confirmed-peer reset 清除範圍。重播輸出目前列出 11 個 fixed-four sites、7 個 component guards；測試仍 4/4 通過，這些仍只是靜態證據，不是 patch 或實機驗收。


## 2026-10-03 receive vector 與擴大 registry 掃描

固定 capture 的無 unwind leaf `0xBC2D10` 已被精確重播：`R8D` 是 selector、`R9` 的 descriptor 轉到 `RDX`、`RCX` 保持 owner/context，callback vector 位於 `0x214C2E0`，entry 168 指向 `0xBABA80`。`0x134D5AC` constructor 會把同一 leaf 寫到 owner `+0xB3F8`；另保存六個 service vector consumers。這收窄了 receive ABI，但不等同 hash→selector registry；`0x4804FCF4` 仍只找到送端 literal。機器收據為 `five_player_feasibility_20260927/receive_dispatch_entry_verification_20261002.json`，`hash_to_selector_proven=false`、`production_hook_ready=false`。

同一固定 build 的已授權程序只讀 registry 搜尋由 128 MiB 擴大至 512 MiB，再至 1 GiB 可讀 `MEM_PRIVATE` 前綴，分別讀取 536,870,912 與 1,073,741,824 bytes，目標 pointer/hash 命中均為 0。工具新增可重播 `--limit-mib/--max-read-mib`，沒有呼叫、寫入、跟隨指標、安裝或注入。收據為 `private_registry_expansion_verification_20261003_1024m.json`，因此仍不能把負面掃描升格為不存在證明。

新增固定版本的 receiver entry xrefs、field xrefs、registration body 與 selector-168 producer scan；producer scan 的整數常數命中不被當作 hash mapping。所有輸出仍維持 `installable=false`、`multiplayer_verified=false`。


## 2026-10-03 public runtime entry audit

新增 `five_player_feasibility_20260927/public_runtime_entry_audit_20261003.py`、`public_runtime_entry_audit_20261003.json` 與中文說明，核對 HD2Runtime package request/release（`0x12FE350`／`0x12FE4E0`）的 exact bytes、Bingus loader、Better Lobby、CChusky 與 RawData。公開入口可重用的只有本機 package residency、Lua discovery/require 和觀察能力；RawData 也證明 logical player resource 只有 9 components，而 Player Clone/Avatar 是 49 components，不能混為同一 admission 結構。報告固定為沒有 public peer admission/player writer/network spawn writer，`eight_player_status=unverified`。

## 2026-10-03 Party／PlayFab 外部容量邊界

新增 `five_player_feasibility_20260927/external_party_playfab_capacity_audit_20261003.py`、JSON 收據、驗證器與 [EXTERNAL_PARTY_PLAYFAB_CAPACITY_20261003.zh-TW.md](../five_player_feasibility_20260927/EXTERNAL_PARTY_PLAYFAB_CAPACITY_20261003.zh-TW.md)。只讀審計固定 build `25480438` 的 `PartyWin.dll`（4,031,520 bytes，SHA-256 `de34667c2f7084013d9c03cd5d1cb5dc3321bc36bb616a845e35534e4e7995e0`）與 `PlayFabMultiplayerWin.dll`（1,878,048 bytes，SHA-256 `95bc5f958e519f612b479de4227f3bdffaba9b2b8de987eb3f7991960b8ced17`）。

`PartyWin.dll` 公開 network configuration、local users、endpoints、endpoint creation、local-user authentication 與 connect API 名稱；`PlayFabMultiplayerWin.dll` 公開 `PFLobbyGetMaxMemberCount`、members/add-member 與 max-member 驗證文字。兩個外部 DLL 都沒有固定事件 `0x4804FCF4` 的 little-endian bytes 或 ASCII 文字命中。官方 Party 文件也描述 user/device 容量可獨立指定，Windows quickstart 有 8 名成員的設定範例；這只支持服務 SDK 與遊戲 native admission 是不同層級，不構成第五至第八個 peer 已建立的證明。

外部服務容量不是目前可安全修改的遊戲入口；`game_native_peer_admission_resolved=false`、`game_native_player_creation_resolved=false`、`installable=false`、`multiplayer_verified=false` 保持不變。下一個必要閘門仍是同一 build 的 hash/event 到 receive selector、`player index=4..7` 建立、所有 client replication 及 cleanup/unwind 的實際 native 呼叫鏈。

## 2026-10-03 player resource／creation patch boundary

新增 [PLAYER_RESOURCE_PATCH_BOUNDARY_20261003.zh-TW.md](../five_player_feasibility_20260927/PLAYER_RESOURCE_PATCH_BOUNDARY_20261003.zh-TW.md) 與固定證據 verifier。18/18 項靜態核對通過：`0x1086460` 對 network index `4..7` 走 fallback，不能到達 `0xFDC140`／`0x608B60` 的 player-resource／roster 建立；player resource 的 component index 239 會進已確認的 `0x540920`，但該插入家族仍是原四槽 guard，map helper 不會配置或擴容，滿表／null bucket 時也沒有可證回滾。property `+0x3B4` 保存 network index，不能用 roster ordinal 代換。

這次核對明確把 `direct_gate_literal_patch_safe=false`、`four_to_seven_sidecar_ready=false`、`relocation_path_ready=false` 固定下來；現有八槽 sidecar 沒有 live player-creation callback，`runtime_verified=false`、`multiplayer_verified=false`。這排除了只改 gate 常數或只掛現有 sidecar 的捷徑，下一個需要的是實際 creation callback ABI、owner-keyed backing、map／cleanup／unwind，以及第五名 peer 的實機呼叫鏈。

## 2026-10-03 receive selector registry 邊界

新增 `five_player_feasibility_20260927/recover_selector_registry_20261003.py`、JSON 與 receipt，重播固定 capture 中全部 8 個 `[RDX+0xB0]` registration call sites，其中 7 個可分類為靜態 hash 或動態 EDX 來源。`0x134D69E` 起的六個 constructor registration 與 `0x14EE278` 的另一個 registration 使用靜態 hash；`0x10946A4` 同形 registration 則由 caller 透過 `EDX` 提供 runtime 值。`0xBC2D10` callback vector 仍逐 byte 核對為 table `0x214C2E0`、selector 168→`0xBABA80`，而 `0x4804FCF4` 在 bounded capture 只命中 `0xBE4981` 送端。

這縮小了 registry 缺口，但沒有取得 service heap、runtime callback state 或 hash→selector 實際 trace；`hash_to_selector_proven=false`、`service_registry_captured=false`、`production_hook_ready=false`、`installable=false`、`multiplayer_verified=false` 保持不變。不能把 registration ABI 形狀當成可安裝 hook。

## 2026-10-03 live dispatcher/session rerun

固定 build `25480438` 的 PID `36536` 完成新的只讀 dispatcher 與 session snapshot 重讀，收據為 `five_player_feasibility_20260927/live_capture_rerun_verification_20261003.json`，12/12 通過。dispatcher 的兩個命中仍是 send-side event hash `0x4804FCF4`（RVA `0xBE4982`）與 receiver pointer `0xBABA80`（RVA `0x214C820`）；session 仍只有 1 個 peer，文件化 roster 仍為 4 槽，4..7 維持合約外。

同一 PID 的 1 GiB `MEM_PRIVATE` registry 掃描在程序消失後沒有產生結果檔，已保存 `live_private_registry_20261003_rerun.failure.json`。這被明確標成未完成嘗試，不推斷 registry 陰性，也沒有呼叫、寫入、hook、注入、安裝或多人驗收。

## 2026-10-03 dynamic registration caller boundary

新增 `five_player_feasibility_20260927/dynamic_registration_caller_audit_20261003.json` 與可重播腳本。固定 code capture 中沒有直接 `E8` caller 指向 dynamic registration body `0x1094680`；該 body 的 hash／selector 仍由 caller 以 `EDX` 在 runtime call boundary 提供。七個 static registration immediate 也沒有 `0x4804FCF4`。4/4 checks 通過，但 `hash_to_selector_proven=false`、`installable=false`、`multiplayer_verified=false` 維持不變。

## 2026-10-03 fresh live registration-state scan

重新啟動原版固定 build `25480438` 的 PID `6884` 後，完成 dispatcher 與 session 的只讀捕獲，以及兩次私有區掃描。128 MiB 基線與包含 receiver／insert／platform-member 指標、`0x4804FCF4` 和七個 static registration hash 的未截斷約 1 GiB `MEM_PRIVATE` 掃描均為 0 命中；`live_registration_state_verification_20261003.json` 的 12/12 checks 通過。

此程序當時仍在空 menu baseline（peer count `0`），文件化 roster 仍為 4 槽，故這只是更強的有界負面觀察，不能證明 registry 不存在，也沒有取得 hash→selector、第五 peer、player creation、安裝或八人驗收。全程沒有呼叫函式、寫入、hook 或注入。

## 2026-10-03 registration scan correction

先前的 1 GiB registry 12/12 收據已撤回：舊工具以相同的 `limit_mib=1024`／`max_read_mib=1024` 執行，原始輸出實際只有 262141 pages，且沒有 postflight image/module 穩定性欄位；`truncated=false` 不能支持完整負面結論。原始 JSON 保留，但已加上 `audit_correction`，验证收据标记为 superseded。

修正 scanner 现在分开记录读取终止原因、coverage、错误与 postflight。PID `6884` 的修正版 128 MiB 重读达到请求上限，但 postflight 未能证明 module list 稳定，因此也保持 `incomplete`；当前没有任何有效的 registry-negative、hash→selector、安装或多人成功结论。详见 `five_player_feasibility_20260927/registration_scan_correction_20261003.json`。

## 2026-10-03 corrected scanner validation

新原版 PID `41576` 以修正 scanner 完成 16 MiB readable `MEM_PRIVATE` prefix：`coverage_complete=true`、`postflight_verified=true`、executable/module/disk identity 全部保持一致，目标指针、事件 hash 与七个 static registration hash 均 0 命中；收据 `live_registration_state_16m_verification_20261003.json` 11/11 通過。

同一 PID 的 dispatcher/session 捕获仍只有 code-side send/receiver hits、1 個 peer 與 4 槽文件化 roster。這證明校正工具的有界負面觀察流程有效，但不證明整個 registry 不存在，也不提供第五 peer、player creation、安裝或八人任務驗收。

## 2026-10-03 原生載入邊界審計

新增 [NATIVE_LOADER_BOUNDARY_20261003.zh-TW.md](../five_player_feasibility_20260927/NATIVE_LOADER_BOUNDARY_20261003.zh-TW.md) 與只讀機器收據 `native_loader_boundary_20261003.json`。固定 build `25480438` 的官方鏈（`helldivers2.exe`、`game.dll`、Party、PlayFab、Steam、Lua）可辨識，但沒有找到受支援的使用者原生 loader 或 production native entry；`game.dll` 的唯一 named export 是 `get_plugin_api`，其合法 caller、callback ID 31 的返回物件與 lobby/player admission 用途仍未閉合。審計也記錄安裝目錄內的 Havoc、HH.sys、pyinjector、dxgi 等疑似注入工具檔案，全部標記為 disallowed injection artifacts，未納入任何實作或啟動路徑。`read_only=true`、`process_started=false`、`process_mutated=false`、`installable=false`、`multiplayer_verified=false` 保持不變。

## 2026-10-03 官方原生 Plugin 目錄發現

新增 [NATIVE_PLUGIN_DIRECTORY_AUDIT_20261003.zh-TW.md](../five_player_feasibility_20260927/NATIVE_PLUGIN_DIRECTORY_AUDIT_20261003.zh-TW.md) 與收據 `native_plugin_directory_audit_20261003.json`。固定 build 的 `bin/plugins` 含官方 `level_generation_pluginw64_release.dll` 與 `wwise_pluginw64_release.dll`，兩者都 export `get_plugin_api`；這證明存在官方原生 plugin ABI 候選，應優先於未知注入路徑研究。它仍沒有提供自訂 plugin 的合法載入證據，也沒有 Session、peer admission、player creation 或 network spawn writer。沒有新增、載入或執行 plugin；`custom_mod_entry_proven=false`、`player_admission_proven=false`、`installable=false`、`multiplayer_verified=false`。

## 2026-10-03 OfficialPlugin ABI 骨架

新增 `eight_player_candidate_20260927/Native/OfficialPlugin`：依 Autodesk Stingray 公開 `engine_plugin_api` 介面，提供固定 `PLUGIN_API_ID=0`、`C_API_ID=31` 的最小 `get_plugin_api` DLL、版本化 callback table、unload 清理與本機 stub harness。`ep_official_plugin_test.exe` 已通過 API ID、未知 ID 拒絕、C API callback 捕獲和 unload 清除四項合成檢查。

## 2026-10-03 authoritative network-index binding

`Native/Bridge`、`Native/Sidecar` 和 `Native/ClientSidecar` 現在要求 Session／Party caller 提供精確的 network index；`ep_sidecar_reserve_at()` 只接受 `0..7`，禁止以本機第一個空槽替代。離隊、重連與 cleanup retry 都攜帶 generation；release 失敗會保留 slot／owner lease 直到可重試，pending cleanup 期間的重複 admission 會被拒絕。收據為 `Native/Bridge/network_index_binding_receipt_20261003.json`。

這仍是離線 bridge 候選：沒有真實 Session／Party allocator、第五至第八個 peer、Player Clone 或客戶端 entity replication 證據，`production_executable=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false`。

## 2026-10-03 OfficialPlugin runtime bridge integration

`Native/OfficialPlugin` 已把 consumer executor 與 native callback binder 編入同一 DLL，提供 preflight／install／remove 及 bind／get／unbind exports。resolver 的 compact view 固定為 `ids[0..7]` 位於 `+0x00`、count 位於 `+0x40`，並明確與 `EP_SIDECAR` layout 分離；preflight 與 bind 都不寫入遊戲記憶體。收據為 `Native/OfficialPlugin/official_plugin_runtime_bridge_receipt_20261003.json`。

這只完成固定 build 的 ABI 候選與合成測試，resolver owner lifetime、Party admission、player creation、cleanup、客戶端 replication 和任務全流程仍未綁定，所有正式多人門檻維持 false。

這個 DLL 只保存 `get_engine_api(31)` 返回指標，不呼叫遊戲函式、不讀寫遊戲程序、不建立 peer 或 player entity。它是合法官方 plugin 入口的 ABI 骨架，不是可玩的八人 Mod；報告 `official_plugin_probe_report_20261003.json` 仍固定 `production_executable=false`、`custom_mod_entry_proven=false`、`player_admission_proven=false`、`installable=false`、`multiplayer_verified=false`。下一閘門是固定 build 的 `ScriptApi`／`GameSessionCApi` layout 與受許可的 plugin 載入觀察，之後才可把 sidecar 接到實際 admission/creation callback。

## 2026-10-03 Official Plugin → GameSession 路線

新增 [OFFICIAL_PLUGIN_GAME_SESSION_ROUTE_20261003.zh-TW.md](../five_player_feasibility_20260927/OFFICIAL_PLUGIN_GAME_SESSION_ROUTE_20261003.zh-TW.md)。公開 Stingray C API 確認 `C_API_ID=31` 的 `ScriptApi` 有 `Network` slot `+0x38`、`GameSession` slot `+0x40`，而 `GameSessionCApi` 具備 `add_peer`、`num_peers`、`peer`、`remove_peer`、`create_game_object`、`migrate_game_object` 等方法。這是目前最實際的合法實作路線，但只是通用 ABI；HD2 實際 table、Party member 到 GameSession 的事件與第五至第八個 Player Clone 建立仍未證明。現有 probe 只保存 table 指標，不呼叫任何遊戲 API；`game_session_table_observed=false`、`player_admission_proven=false`、`installable=false`、`multiplayer_verified=false`。

## 2026-10-03 官方插件載入邊界已在實機觀察

固定 build `25480438` 的遊戲程序 PID `20472` 實際載入倉庫建置的 `eight_player_pluginw64_release.dll`。插件 runtime log 記錄到官方 loader 呼叫 `get_plugin_api` 的 API id `0`、`18`、`19`，並完成 `loaded` callback；這確認官方 plugin directory 的 ABI 入口可由自建探針觀察。模組列表同時保留官方 `level_generation_pluginw64_release.dll` 與 `wwise_pluginw64_release.dll`。

探針在 `loaded` callback 只查詢 `C_API_ID=31`。本次 callback path 回傳 null，`Network` 與 `GameSession` table pointer 都是 null，因此沒有進入任何遊戲函式、peer admission 或 player creation。探針沒有寫入記憶體、安裝 hook、注入模組或改動官方 DLL。完整原始 JSON Lines 收據見 [live_official_plugin_probe_runtime_20261003.jsonl](../five_player_feasibility_20260927/live_official_plugin_probe_runtime_20261003.jsonl)，彙整結果見 [LIVE_OFFICIAL_PLUGIN_PROBE_20261003.zh-TW.md](../five_player_feasibility_20260927/LIVE_OFFICIAL_PLUGIN_PROBE_20261003.zh-TW.md)。

因此這次只把 `runtime_verified` 與 `custom_mod_entry_proven` 標記為 true；`player_admission_proven`、`player_creation_proven`、`installable`、`multiplayer_verified` 仍為 false。下一個實作邊界是找出 `C_API_ID=31` 在官方 plugin callback path 回傳 null 的原因，取得版本鎖定的 `GameSession`/peer admission callback 合約後才可設計可回滾的 sidecar。

## 2026-10-03 `setup_game` C API 已取得

在固定 build `25480438` 的 PID `42132`，官方 loader 先於 `loaded` callback 回傳 null，之後在公開 `PluginApi.setup_game` callback 取得非 null 的 `ScriptApi`、`Network` 與 `GameSession` table pointer。這修正了先前把 `loaded` 當作唯一入口的假設；原始 JSON Lines 與收據保留於 [R2 證據](../five_player_feasibility_20260927/LIVE_OFFICIAL_PLUGIN_PROBE_20261003_R2.zh-TW.md)。

## 2026-10-03 GameSession 唯讀 getter 已實機呼叫

在 PID `38132` 的同一固定 build，探針於 `setup_game`／bounded `update_game` 路徑呼叫公開 `NetworkCApi.game_session()` 和 `GameSessionCApi.num_peers()`。記錄到 GameSession 從 `null` 變為 `0x1900edd7e90`，peer count 當時為 `0`。沒有呼叫 `add_peer`、`remove_peer`、`create_game_object`，也沒有寫入、hook 或注入。完整收據見 [R3](../five_player_feasibility_20260927/LIVE_OFFICIAL_PLUGIN_PROBE_20261003_R3.zh-TW.md)。

這使下一個安全邊界成為 `peer_self`／`peer` 唯讀觀察與 player creation/roster callback 解析；第五至第八名玩家、可安裝版本和多人全流程仍未驗收。

## 2026-10-03 capacity patch 下的 Peer 狀態觀測

固定 build `25480438` 的 capacity patch plugin 以官方 plugin ABI 載入，35 個已核對的四人 capacity、enumeration、join、state、migration sites 在同一事務中改為 8，並完成 `GameSession` 唯讀觀測。原始資料保存於 [live_capacity_patch_runtime_20261003_peer_slots.jsonl](../five_player_feasibility_20260927/live_capacity_patch_runtime_20261003_peer_slots.jsonl)，驗證收據為 [live_capacity_patch_peer_state_20261003.json](../five_player_feasibility_20260927/live_capacity_patch_peer_state_20261003.json)。

這次 bounded run 讀到 `peer_count` 由 0 遞增至 16，但八個 `peer()` 讀值全部相同（`0x7ff7bf855b70`）。因此目前不能确定 `num_peers` 是否为玩家数量，也不能把这次计数当作第 5 至第 8 个账号已加入的证据；`peer_id_semantics_unresolved=true`、`count_is_not_player_admission=true`。插件没有调用 `add_peer`、`remove_peer`、`create_game_object`，也没有写入 Party/PlayFab 或建立 Player Clone。

capacity patch 仍是 disabled-by-default、固定 build 的研究候选；inline storage、confirmed-peer/client roster、player creation、实体复制、死亡/增援、重连、撤离、结算及 host migration 仍未闭合。`player_admission_proven=false`、`player_creation_proven=false`、`installable=false`、`multiplayer_verified=false` 保持不变。下一步应先解析 `PeerId`/`peer()` 的实际语义并取得真实 admission callback，再把八槽 sidecar 接入 creation 与 cleanup 链。

## 2026-10-03 no-call Session snapshot integration

`Native/SessionObservation` 已接入官方插件。`setup_game`／bounded update 现在先通过固定 EXE、Network getter、GameSession 底层 vtable 与 record layout fingerprint，再以进程内只读复制获取最多八条 opaque record；任何不匹配、count 超过 8、backing 缺失或双读变化都 fail-closed。此路径不调用 `peer`、`num_peers`、`in_session` 或 `host`，也不写入游戏状态。

这只提供固定版本的 layout 观察工具，不是玩家 admission 或 Player Clone 建立。当前第五至第八个账号、客户端复制、死亡/增援、重连、结算和 host migration 仍未验证；`installable=false`、`multiplayer_verified=false` 保持不变。最新研究提交为 `2136c72`，状态收据提交为 `0037825`。
## 2026-10-03 player creation gate ABI adapter

新增 `Native/PlayerCreationGate` 固定 build `25480438` 的版本門控候選。它要求 `game.dll+0x1086460` 的 9-byte gate fingerprint，以及 `0xFDC140` resource/component dispatch 和 `0x608B60` roster dispatch 的 downstream fingerprints；只有 caller 提供的 owner、resource、component、roster、cleanup、rollback、quiesce、write 與 readiness callbacks 全部有效時，才允許把 gate immediate 從 `4` 暫時改為 `8`。寫入與恢復完全由 caller-supplied backend 執行，模組本身不取得程序 handle，也不呼叫 `VirtualProtect` 或 `WriteProcessMemory`。

`ep_player_creation_gate_synthetic_passed` 與 receipt verifier 已通過：network index `0..7`、index `8` 拒絕、重複 identity、generation/owner lease、resource/component/roster rollback、cleanup retry 及 exact-byte restore 均有測試。這仍不是獨立可玩的 patch；真實 downstream ABI、四人 component backing relocation、confirmed-peer receiver、client replication 和完整任務生命週期尚未接線，因此 `production_executable=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false` 維持不變。收據為 `Native/PlayerCreationGate/player_creation_gate_receipt_20261003.json`，整合提交為 `30ca8c0`。

## 2026-10-03 player resource → native bridge transaction adapter

新增 `Native/PlayerResource/ep_resource_bridge_adapter.*`，把八格 player-resource sidecar 的三階段 callback table 接到既有 `EP_NATIVE_BRIDGE` admission/depart/reconnect contract。transaction 順序固定為 `resource_begin → native_confirm → native_create → first → second → third → resource_publish`；任何 callback、metadata、version/size、generation 或 stage failure 都 fail-closed，並由 bridge 的 remove compensation 清除 native 與 sidecar identity。離隊先執行 native remove，再釋放 resource record；network index 由 caller 提供並逐項保留，禁止以 local first-free 或 roster ordinal 代換。

`ep_resource_bridge_adapter_synthetic_passed`、原 player-resource test、Bridge/client integration 與 Python receipt checks 已通過，覆蓋八筆 admission、index 4 departure/reconnect、index 3 stage failure rollback 和完整 owner cleanup。這是離線 ABI-shaped transaction，不是 live callback binding；沒有解析 RVA、呼叫 game.dll、安裝 hook、建立第五至第八 peer 或驗證 client entity replication。`production_executable=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false` 維持不變。收據為 `Native/PlayerResource/resource_bridge_adapter_receipt_20261003.json`，整合提交為 `9715a41`。

## 2026-10-03 MidGate owner／capacity ABI correction

重新以 x64 反組譯核對後，MidGate 兩個 helper call 的 owner 來源是原生中段的 `R9`，正確搬移為 `49 8B C9`（`mov rcx,r9`）；先前 `4C 8B C9` 其實是反向搬移，synthetic wrapper 因原本保留 `RCX` 而未暴露這個錯誤。index 搬移維持 `41 8B D6`（`mov edx,r14d`）。capacity stub 現在在比較前無條件建立 `ECX=8`，再把合法／非法 occupancy 結果交回原本的 `sub ecx,eax` continuation。

`ep_midgate_executor_synthetic_passed`、DLL export load check 和 MidGate Python 4/4 均重新通過；合成測試另覆蓋 owner 不從錯誤寄存器取得、partial remove、獨立 site restore 和 retry cleanup。這仍是 caller-supplied helper/quiescence 的固定 build 候選，沒有遊戲程序存取、真實 callback 綁定、安裝或多人驗收。`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 維持不變。整合提交為 `5c879a9`。

## 2026-10-03 underlying GameSession vtable bounded observation

新增 `Native/SessionObservation/ep_session_vtable_snapshot.h` 與合成 harness，針對保存的固定 build vtable capture 建立不呼叫函式的 bounded reader：`helldivers2.exe+0x292BE0` 的 slot `0x70` 讀取 object `+0x138` count，`+0x292BF0` 的 slot `0x78` 對 `+0x140` table 使用 `0x30` stride，slot `0x98`／`+0x292CC0` 讀取 `+0x130` opaque owner。它會核對 EXE PE identity、function prefix、count `<=8`、record pointer 唯一性，並穩定重讀最多八筆 `0x30` bytes opaque record；任何漂移都 fail-closed。

`session_vtable_snapshot_synthetic_passed` 已通過，收據為 `Native/SessionObservation/session_vtable_snapshot_receipt_20261003.json`。record 尚未解碼成 PeerId、network index 或玩家，也沒有呼叫 `add_peer`、`remove_peer`、`create_game_object`、player creation 或 client replication；這是下一個真實 admission callback 解析的版本化觀測邊界，不是八人成功證據。

## 2026-10-03 admission call-shape contract

新增 `Native/SessionMembers/admission_boundary_contract_20261003.py`、JSON 收據、中文說明與 2 項 Python 合成測試，固定保存的 `host_expansion_disasm_108d9f0.json` 中兩個最接近 admission 的間接呼叫：`game.dll+0x3326308` 介面表的 `+0x08`／`+0x50`，同一個 `[network_context+0xB390]` owner、`[r12]` 不透明 ID、`[r12+0x20]=7` 狀態寫入，以及後續 `0xA497A2DD`／`0x8FE70196` dispatcher hash。

這只固定 bytes、RVA、反組譯文字與來源 SHA-256；兩個 target 的實際函式、回傳值、PeerId／network index、拒絕／cleanup、player creation、client replication 與 host migration 仍未解析。全程沒有啟動或存取遊戲程序、呼叫函式、寫入記憶體或安裝 hook，`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 維持不變。

## 2026-10-03 MidGate helper-register ABI correction

重新核對 `Native/MidGate` 的兩個 machine-code template 後，修正 helper 呼叫前的 `mov edx,r14d` bytes：正確編碼是 `41 8B D6`；舊候選的 `44 8B D6` 會解碼為 `mov r10d,esi`，並沒有傳遞 native index。容量與 allocator template、固定收據和 verifier 已同步重生成，Python static checks 4/4 通過。

本機另外以 caller-supplied synthetic image 編譯執行器，`ep_midgate_executor_synthetic_passed` 與 DLL export load check 均通過；這只驗證固定 PE/fingerprint gate、兩個 reversible detour、x64 unwind registration、helper ABI 和 exact restore。執行器沒有取得遊戲程序、沒有安裝到 `game.dll`，也沒有綁定真實 owner/quiescence、confirmed-peer、player-creation 或 client replication callback；`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 仍是有效狀態。

## 2026-10-03 player creation rollback hardening and admission boundary continuation

本輪只在離線固定版本資料與合成 harness 上工作，沒有啟動或存取遊戲程序，沒有呼叫、寫入、hook、注入、安裝或多人驗收。

- `Native/PlayerCreationGate` 的版本門控 adapter 升為 `EP_PC_VERSION=2`，對失敗 admission 增加 `rollback_pending` 狀態。已完成 callback 但補償失敗時，slot 保持 `REMOVING` 並由 `ep_pc_depart` 重試同一 rollback；本地 commit invariant 失敗時會補償已完成 callback，避免 ACTIVE slot 或 owner lease 遺留。`ep_player_creation_gate_synthetic_passed` 與 receipt verifier 通過。
- `Native/SessionObservation` 新增 `ep_session_record_semantics` 邊界驗證：session `+0x138` count、`+0x140` table、`0x30` stride、record `+0x00` opaque identity token、session `+0x20` self key、owner `+0x130` 與 record `+0x29` byte 的穩定讀取與重複 token rejection 均可重播。這些仍不是 PeerId、network index 或玩家語義，也沒有呼叫任何 GameSession writer。
- `Native/SessionMembers` 新增 admission/dispatch/cleanup 靜態交叉契約：host `+0x08`／`+0x50` 間接呼叫、host-to-client 四筆 `0x38` stride dispatch、5..7 candidate gate、`0xBE4910` sender、`0xB90B20` client insert、join-handler nested call 與 `0x13EFF30` reject/cleanup candidate 已固定。target 語義、return ABI、cleanup ABI、第五至第八 peer admission、player creation、replication 與 migration 仍未解析。

離線證據與合成測試不能替代實機多人驗收。正式狀態仍為 `installable=false`、`multiplayer_verified=false`；下一步先取得允許的唯讀 callback/owner/cleanup ABI 證據，再把 producer、confirmed-peer、player creation、client replication 與 rollback/unwind 綁定，之後才可進行五至八帳號階梯。

## 2026-10-03 client fixed-four inventory and bounded peer reader continuation

本輪仍只使用倉庫內固定 build 證據與合成 harness，沒有啟動或存取遊戲程序，沒有呼叫、寫入、hook、注入、安裝或多人驗收。

- `five_player_feasibility_20260927/client_fixed_four_inventory_20261003.json` 固定客戶端 confirmed-peer 的五組四槽陣列：`+0x10/+0x18` stride 8、`+0x38/+0x40` stride 16、`+0x80/+0x88` stride 16、`+0xC8/+0xD0` stride 32（record `+0x14`），以及 `+0x150..+0x190` peer-keyed 區。append、remove/neighbor compaction、primary/secondary reset、kicked 與 host migration handoff 均已列出；10/10 replay 與 3 個 Python tests 通過。這是四槽 reader/writer inventory，不是 network index 語義或可安裝 patch。
- `Native/SessionObservation/ep_session_record_consumer_contract.py` 對 session vtable 的 count/table/token/byte `+0x29` instruction consumers 做 bounded xref。保存資料沒有直接 target RVA，可重播結果明確為 negative/bounded，不能把 opaque record 推成 PeerId 或 player index；3 個 tests 通過。
- `Native/OfficialPlugin` 新增只讀 `official_peer_reader_contract_20261003.json`。它只接受穩定 opaque snapshot 與 record semantics，提供 bounded `get_peer_count/get_peer_record`；版本、owner lease、quiescence、cleanup、index 與 count 失敗均 fail-closed，明確禁止 `add_peer`、`remove_peer`、`create_game_object`。`official_peer_reader_contract_synthetic_passed` 通過，但不構成 admission 或角色建立證據。

上述三項進一步閉合了離線固定四槽與安全觀測邊界，仍未閉合第五至第八 peer 的原生 admission、client replication、Player Clone 建立、生命週期與撤離結算。因此 `installable=false`、`multiplayer_verified=false` 維持不變。\n\n## 2026-10-04 離線契約收尾：admission 狀態語義、建立交易互斥、客戶端複製與 AI fallback\n\n本輪仍沒有啟動或存取遊戲程序，沒有注入、寫入、安裝或多人驗收。以下產物只把固定 build `25480438` 的已知邊界收斂成可重播契約，不能取代真實 callback 綁定或八客戶端任務收據。\n\n- `Native/SessionMembers/admission_callback_abi_contract_20261003.*` 及對應測試固定兩個 host 間接呼叫的 x64 callback 位置、六個參數位置與 nested probe 分支。先前將 dispatcher 的 `record+0x20` 狀態值誤寫成 `network index 5..7` 已更正：`state < 5` 跳過，`state >= 7` 只產生旗標，沒有 `5..7` 的上限檢查；PeerId、network index、target return、cleanup 與成功語義仍未解析。admission 合約測試與原有 dispatch cleanup 測試共 11 項通過，所有正式門檻保持 false。\n- `Native/PlayerCreationGate` 升為 `EP_PC_VERSION=3`。`admit`、`depart`、patch prepare/install/remove、destroy 都受 operation guard 保護；外部 cleanup/rollback callback 執行期間，同執行緒重入與 worker thread 重疊呼叫回傳 `EP_PC_BUSY`，不會重複清理、釋放 owner 或覆寫 live adapter。live re-init 也拒絕覆蓋未銷毀的 adapter。C++ harness 與 receipt verifier 通過；這仍是 caller-owned offline ABI adapter。\n- 新增 `Native/ClientReplication` sidecar 契約：五組已知客戶端陣列以獨立 ordinal view 表示，stable network index 固定 `0..7`，保留洞位、generation、rollback retry、callback lease/quiescence 與 host-migration transaction；`ep_cr_production_enabled()` 固定回傳 0。C++ synthetic marker、3 項 Python tests 與 receipt replay 通過。它沒有 native entity callback、Party admission、player creation 或 runtime writer。\n- 新增 `ai_scaling_contract_20261003.*` 與精簡來源 snapshot。固定提交的 RawData 來源含 247 個 `player_count_multipliers`，全部為四項；契約只允許 1..4 直接索引、5..8 重用第 4 項，錯誤 count/vector、版本或雜湊 fail-closed，host/client 輸入必須完全一致。21 項 tests 及 receipt replay 通過；這不是當前 native AI consumer 已證明的行為，runtime activation 仍關閉。\n\n下一步不變：先從允許的唯讀 runtime evidence 綁定 admission target/return/cleanup、confirmed-peer receiver、player resource/component/roster 建立、client entity replication 與 owner quiescence；完成第五人後才可逐級測試第六至第八人，並以八個獨立帳號的同任務全流程收據決定是否開啟 installable/multiplayer gates。\n

## 2026-10-04 建立與 resource 初始化失敗路徑修正

固定 build `25480438` 的離線測試又發現兩個會掩蓋真實 ABI 問題的生命週期漏洞，已修正並重建：

- `PlayerCreationGate.ep_pc_admit` 在本地 `validate_locked` 失敗時，現在會先清除剛保留的 `PENDING` 槽位與 inflight reservation，再返回原始 invariant 錯誤；此時尚未 retain 外部 owner，因此不會呼叫虛構 rollback/release。重複 identity、非法 index 等尚未建立 reservation 的拒絕則直接返回。測試新增 pre-commit invariant failure regression。
- `PlayerResource.ep_resource_init` 遇到 live magic 現在回傳 `EP_RS_BUSY`，不再用 `memset` 抹掉 active/PENDING record、generation 或 owner lease；caller 必須提供 zero-initialized storage，destroy 後才可重用。Bridge/resource receipt 與報告已重算二進位與來源雜湊。

PlayerCreationGate、PlayerResource、resource bridge 的 C++ marker 與 Python receipt tests 均通過。這些修正仍只作用於 caller-owned offline sidecar；真實 admission/creation/replication callback、遊戲安裝與八帳號任務尚未驗證，正式 gates 維持 false。

## 2026-10-04 Native Bridge allocator release retry

修正 `Native/Bridge` 的另一個離線生命週期漏洞：Session/Party allocator 已回傳 index、但 sidecar 尚未建立時，如果第一次 `release_index` 失敗，舊路徑會只返回錯誤並丟失 authoritative index 與 owner lease。現在 bridge 會保存 generation-zero allocator-only cleanup record，保留 peer、resource handle、index 與 owner lease；`ep_bridge_retry_cleanup` 完成 release 後才清除記錄並釋放 owner。重複 identity 在 retry 前仍會被阻擋，正常 generation token cleanup 行為不變。

合成 harness 新增 invalid allocator index、release failure、duplicate block 與 retry recovery；`ep_native_bridge_synthetic_passed`、跨元件 integration marker 與 Python report test 通過。這仍未綁定真實 Session/Party allocator 或遊戲 callback ABI，`installable=false`、`multiplayer_verified=false` 不變。

## 2026-10-04 ClientSidecar adapter 初始化生命週期修正

`Native/ClientSidecar/ep_client_adapter_init` 原本會對 live adapter 無條件 `memset`。現在若 adapter 仍 initialized 會返回 `EP_BRIDGE_ALREADY_READY`，保留 authoritative index reservation、client record 與 owner refs；必須先 destroy，並由 caller 提供 zero-initialized storage 才能重建。測試在已保留 index 後重初始化，確認 reservation 未被抹除；sidecar/adapter marker 與 Python report tests 通過。真實 client callback、entity replication 與多人驗收仍未接線。

## 2026-10-04 實機探針啟動嘗試

依使用者授權暫時部署唯讀 `eight_player_pluginw64_release.dll` 並啟動固定 Steam build。含自訂 DLL 的程序 PID `39916` 與移除自訂 DLL 後的官方程序 PID `18216` 均顯示 `Fatal Error!`，沒有新的探針 log、GameSession、peer 或玩家建立資料。自訂 DLL 已移回 workspace 證據目錄；官方插件未修改，容量 patch 未啟用，兩個程序已停止。這是啟動環境失敗，不是多人拒絕或成功；`installable`、`runtime_verified`、`multiplayer_verified` 保持 false。完整記錄見 `five_player_feasibility_20260927/LIVE_PROBE_ATTEMPT_20261004.*`。


## 2026-10-04 allocator overflow 與實機 no-call 邊界

最新遠端提交為 `67d32de`。`Native/Bridge` 與 `Native/ClientSidecar` 現在保留 allocator 回傳的 authoritative index（包括 `index >= 8` 的 generation-zero compensation），allocator 失敗但回傳非 `0xFF` 時會立即補償或留下可重試 cleanup；已保留的 index collision 不會被誤釋放。Bridge、ClientSidecar、跨元件 preflight 與 Python receipt tests 均通過，但仍是 caller-owned offline contract，沒有真實 Session/Party callback。

`Native/OfficialPlugin` 的固定 build getter gate 現在只檢查 PE/SHA-256、C API/table 可讀性、`game.dll+0x34fdf0` 及 15-byte machine-code fingerprint、可執行頁與穩定重讀；不再呼叫 getter 或解碼 session/peer。先前呼叫版本在實機啟動時出現 Fatal Error，因此保留 no-call fail-closed 邊界。最新實機重試 PID `15724` 仍顯示 `Fatal Error!`，清空後的探針暫存檔沒有新回呼；自訂 DLL 已移除，官方 plugins 未修改。

可核對資料：`five_player_feasibility_20260927/LIVE_PROBE_ATTEMPT_20261004.*`、`Native/OfficialPlugin/official_plugin_runtime_bridge_receipt_20261003.json`、`Native/IntegrationPreflight/integration_preflight_receipt_20261004.json`。目前 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`；下一步先診斷固定 Steam build 的 Fatal Error／合法 plugin 載入時序，再取得允許的 admission callback/owner/cleanup ABI，之後才做第五至第八帳號階梯。

## 2026-10-09 configurable capacity contract and menu boundary

新增 `eight_player_candidate_20260927/Source/player_capacity_contract.lua` 與
`player_capacity_menu.lua`。Lua contract 統一 1～目前已驗證容量、4/5/8/12/16 preset、
`effective_max_players` 最小值計算、host authority、metadata、pending/apply/rollback、
任務中升容預留與任務中降容拒絕。Menu adapter 以 Bingus Shared Loader 啟動，透過
Mod Options Menu 註冊 `Player Capacity`，顯示設定上限、已加入人數、可用槽位、有效
上限、房主權限、客戶端相容性與設定狀態；沒有 Native bridge 時只顯示診斷並拒絕容量
變更。

新增 `Native/CapacityContract` C ABI，並把 `Native/Bridge` 的 preflight 與 admission
接到這個契約。allocator 回傳超過有效容量的 authoritative index 時，bridge 會先做
generation-zero compensation，再返回容量拒絕；不會改用本機第一個空槽。C++ harness
輸出 `ep_capacity_contract_passed`、`ep_native_bridge_synthetic_passed` 與
`ep_bridge_client_integration_passed`，staging 與 Lua smoke checks 也通過。

套件 metadata 現在列出 Bingus Shared Loader >=18、Mod Options Menu >=1.1、HD2Runtime
>=0.28.0、4/5/8/12/16 verified presets 與 16 hard storage limit。這些是離線設定與
bridge 邊界，尚未取得真實 Session/Party writer、第五至第八個 Player Clone、client
entity replication 或同任務生命週期證據；`installable=false`、`runtime_verified=false`、
`multiplayer_verified=false` 必須保持不變。
## 2026-10-09 16-slot bounded storage continuation

在先前的 4/5/8/12/16 Lua 容量契約與選單候選上，Native storage 現已提升到
16 槽硬儲存上限：`Native/Sidecar`、`Native/ClientSidecar`、
`Native/ClientReplication` 與 `Native/PlayerResource` 都使用同一份
`EP_CAPACITY_HARD_LIMIT=16`；每次交易的 active bound 仍由
`EP_CAPACITY_CONTRACT.effective_max_players` 決定。Sidecar 新增
`ep_sidecar_init_capacity()`，Native Bridge 在 init 時複製 contract，避免呼叫者
之後修改或釋放 contract 造成容量漂移，admit/reconnect 前也重新檢查 contract、
sidecar bound 和 invariant。

同一輪修正 ClientReplication ordinal sentinel 的初始化，並重新建置通過：
`ep_sidecar_synthetic_passed`、`ep_native_bridge_synthetic_passed`、
`ep_bridge_client_integration_passed`、`ep_client_sidecar_synthetic_passed`、
`ep_client_bridge_adapter_synthetic_passed`、
`ep_client_replication_contract_synthetic_passed`、
`ep_player_resource_synthetic_passed`、
`ep_resource_bridge_adapter_synthetic_passed`；相關 Python report/hash tests
也通過。

這只擴大隔離資料結構的安全儲存範圍，並沒有替真實遊戲移除 4 人限制。已知
`PlayerCreationGate` 的固定 build patch、Session/Party allocator、confirmed-peer
ABI、Player Clone 建立、client entity replication、安裝、實機及八帳號任務全流程
仍未閉合。`production_executable=false`、`runtime_verified=false`、
`installable=false`、`multiplayer_verified=false` 必須保持不變。

## 2026-10-09 dynamic MidGate capacity continuation

`Native/MidGate` 的 capacity 與 allocator machine-code stub 已改為接受獨立的
`limit` callback，將有效上限夾在 `1..16`，再把 occupied count、authoritative
network index、原生 `-1` sentinel 與 continuation 所需的寄存器完整恢復。capacity
stub 現在使用 116-byte code，allocator stub 使用 122-byte code；owner 由非揮發
寄存器保存，allocator 也保存原本的 destination `rdx`。這移除了中段模板內固定 8
的比較，讓 Lua/Native 容量契約可以在同一 ABI 邊界傳遞 4、5、8、12 或 16 的已驗證
設定值。

`ep_midgate_executor_synthetic_passed`、DLL export load check、MidGate Python
static verifier 4/4 與整合收據重算均通過。這仍是固定 build 的 caller-owned
machine-code 候選：真實 limit/occupancy/allocator owner、confirmed-peer receiver、
Player Clone、client entity replication、thread quiescence 與八帳號同任務驗收尚未
綁定，因此 `executable=false`、`installable=false`、`runtime_verified=false`、
`multiplayer_verified=false` 維持不變。

## 2026-10-10 Lua/native capacity-control boundary

新增 `Native/CapacityControl/ep_capacity_control.h/.cpp` 及固定版本的控制層，並把
它編入 OfficialPlugin 的建置命令。這一層不是猜測的 HD2 callback：provider 必須先
以 ABI、owner lifetime、房主／客戶端 epoch、遊戲版本、quiescence 和所有層級容量
完成綁定，否則 Lua 只能看到 `native_provider_unbound` 或 `native_not_ready`。

`ep_control_submit` 會拒絕過期 generation、過期 authority epoch、客戶端、不相容
版本、部分 reservation 及任務中非法降容；`ep_control_boundary` 將 Session/Party、
Peer、Roster、Entity、resource 與 metadata 的變更視為單一 commit。provider 部分成功
或失敗時必須同步 rollback；rollback 失敗會留下 fault bit，阻止 admission、reconnect
和 destroy，直到明確清理。Lua `player_capacity_native.lua` 只解析固定大小的 snapshot/
request，`player_capacity_runtime.lua` 將其接到 HD2Runtime 的 mod log；Menu 會把一次
MODS APPLY 的欄位合成一筆 request，再由 native boundary 原子處理。

離線驗證通過：`Native/CapacityControl/test_capacity_control.py` 3 項、
`ep_native_bridge_synthetic_passed`、`ep_bridge_client_integration_passed`，以及六份
Lua 檔案的語法檢查。這仍是隔離控制邊界，沒有 Session/Party provider、第五至第八個
Player Clone、client entity replication 或多人任務收據；`executable=false`、
`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 必須維持。

同一輪新增 `Package/build_bingus_archive.py`：它依 Bingus Shared Loader v18/API 1
的 Lua archive 格式產生 `Addon/9ba626afa44a3aa3.patch_0`，包含四個固定 hash 的
resource，但只讓 `mods/cainiao/hd2_capacity_menu` 帶 `HD2-Addon` 宣告，另外三個
resource 保持私有 `require` 模組。兩項封裝測試確認 ZIP 可重現、envelope/type/offset
正確、依賴 metadata 存在，以及錯誤宣告會被拒絕。這個封裝仍然只載入選單和安全
FFI client；找不到已載入的 ABI 相符 native provider 時保持 `Rejected`，不能把
Lua archive 視為 Session/Party 或多人完成證據。

OfficialPlugin 的固定版本建置命令現在也編入離線 `ClientReplication` sidecar，讓
其 0..7 network index、pending/confirmed、owner migration、callback lease 和
cleanup 契約可以與容量控制邊界一起編譯；建置通過，但它仍沒有被綁到真實的
confirmed-peer receiver 或 Entity replication callback。

## 2026-10-10 fixed-build live preflight

在使用者授權後，以唯讀方式核對了 `F:\Game\Steam\steamapps\common\Helldivers 2`。
六份固定 build 檔案的 SHA-256 全部相符，`helldivers2.exe` 當時未執行，且沒有
安裝、複製、注入或寫入遊戲檔案；結果保存在
`github_handoff_20260927/live_build_preflight_20261010.json`。結果仍是
`blocked`，唯一 blocker 是現有 `native_peer_admission_plan_20261002.json` 的
`executable=false`。這份檔案只證明版本與停止程序 gate，沒有產生 native provider
或八帳號多人驗收證據。

## 2026-10-10 fixed-build native getter boundary correction

交叉核對 `five_player_feasibility_20260927/live_c_api_table_prefixes_20261003.json` 後，修正 OfficialPlugin 的 Session getter gate：保存的 `0x34fdf0` wrapper 屬於 `helldivers2.exe`，不是 `game.dll`。gate 現在分別核對兩個 PE identity，只有 EXE 的 getter RVA 與 15-byte fingerprint 通過才會進入唯讀觀察；新增 module-boundary synthetic test，並保留 table 重讀、可執行頁、ABI 未證明即不呼叫的條件。

另產生 `five_player_feasibility_20260927/live_c_api_table_map_verification_20261010.json`，核對 GameSession table 的 wrapper prefix 與模組來源。`+0x40`、`+0x50` 等 wrapper 的參數、返回值與副作用仍未證明，不能套用 Autodesk 公開 SDK 的 method 名稱。這一輪沒有啟用 admission、Player Clone、Entity replication 或遊戲記憶體寫入。

本輪試改的 observation 掃描上限已撤回：本地 storage ceiling 不能證明 native 配置範圍。8 是舊掃描上限，並非八名玩家的實機證據；8/12/16 人均未通過多人驗收。

## 2026-10-10 getter gate receipt

新增 `eight_player_candidate_20260927/Native/OfficialPlugin/official_plugin_session_getter_gate_receipt_20261010.json`，記錄 getter 位於 `helldivers2.exe+0x34fdf0`、錯誤 `game.dll` 模組會被拒絕，以及 wrapper 語義、呼叫慣例和返回生命週期仍未證明。測試與建置只使用唯讀 synthetic gate，沒有啟用遊戲函式呼叫。

## 2026-10-10 single-client verification boundary

目前只有一組本機《絕地潛兵 2》帳號與客戶端，沒有可用的第二至第八組獨立登入資料。因此本輪不能執行五人至八人同任務、離隊／重連、房主轉移、撤離或結算驗收，也不能產生 `verify_multiplayer_acceptance.py` 所需的八客戶端證據。`installable=false`、`runtime_verified=false` 及 `multiplayer_verified=false` 保持不變；離線契約測試和版本閘門不構成多人成功。

單客戶端邊界已保存於 `github_handoff_20260927/single_client_verification_20261010.json`，供後續交接核對。

## 2026-10-10 metadata capacity synchronization boundary

補強 Lua 容量 metadata 驗證：Host 廣播現在必須包含 `peer_capacity`、`roster_capacity`、
`entity_capacity`、`resource_capacity`、`network_capacity`、`verified_capacity`、
`apply_mode`、`generation` 與 fingerprints。Client 會重新計算兩端 effective capacity，
拒絕缺少欄位、容量不一致、偽造 effective 值或版本指紋漂移；Package mirror 與 Bingus
archive 已同步更新。這是同步與 fail-closed 邊界的離線修正，沒有增加任何多人驗收證據，
`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 維持不變。
## 2026-10-10 offline capacity contract hardening and package rebuild

本輪修正八人候選容量層的實際 fail-closed 缺口：Lua `stage` 現在拒絕非布林設定旗標與未知 apply mode；`apply` 會重新以目前的 joined players、component capacities、mission lifecycle、quiescence 及 generation 驗證 pending request，不會把過期 pending snapshot 的狀態覆寫回目前 state。Lua generation 上限與 native `UINT32` 對齊，Source 與 Package mirror 的固定 `game.dll` SHA-256 也已同步。

同步更新候選 manifest 的受影響來源指紋與 build-profile manifest pin。修正 `Native/IntegrationPreflight` receipt 測試對 `{bytes, sha256}` 指紋記錄的讀取，並更新該測試的 receipt hash。

離線驗證：capacity contract `17 passed, 3 subtests passed`；整合／封裝／C API dispatch 組合 `48 passed, 7 subtests passed`；Bridge、ClientSidecar、ClientReplication、PlayerResource 組合 `10 passed`；IntegrationPreflight、CapacityControl、Bingus archive `7 passed`。`CapacityControl/build_x64.bat`、`OfficialPlugin/build_x64.bat` 建置成功，getter module-boundary harness 輸出 `ep_official_session_getter_module_boundary_passed`，preflight harness 輸出 `ep_eight_preflight_synthetic_passed`。

已重建 `output/native_dispatch_20261010/hd2_capacity_menu.patch_0`，package SHA-256 為 `5b8c6e91f188c8352e945301635291aeeab2fadd4f2200c89d1b08d2035f39ba`。這些仍是離線候選／封裝證據；provider binding、confirmed-peer、Player Clone、真實 client replication、八帳號任務生命週期均未增加證據。`production_executable=false`、`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 維持不變。
## 2026-10-10 capacity runtime fail-closed hardening

`Source/player_capacity_runtime.lua` 與 Package mirror 現在會拒絕格式錯誤的 native API、缺少 HD2Runtime mod logger、非 table snapshot、非布林容量旗標、未知 apply mode，以及沒有 `{accepted, reason}` 的 provider 回傳；provider 缺失時回傳明確的 `native_provider_unbound`，不會把異常結果當成設定成功。

新增 Lua runtime fixture，涵蓋有效 8 人 request、錯誤旗標、錯誤 apply mode 與 provider log。容量 contract、runtime、Integration、Bingus archive 組合驗證為 `36 passed, 7 subtests passed`；candidate manifest 已擴充並驗證 43 個來源。Source／Package runtime 與 native mirror byte-identical。

重建 archive：`output/native_dispatch_20261010/hd2_capacity_menu.patch_0`，package SHA-256 `143981538920fef3af20a7f1d1b44a8a61a43f78015e5f74a6b9f3a153afcbf9`。仍為 fail-closed staging package，`provider_bound=false`、`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。
## 2026-10-10 configurable-capacity acceptance verifier

`Integration/verify_multiplayer_acceptance.py` 已從固定八人改為支援容量 `4/5/8/12/16`。每份 live client log 必須宣告相同 `capacity`，帳號／client／peer／resource／entity／roster 與 network index 會依該容量驗證；CLI 新增 `--capacity`，預設仍為 8。缺少容量聲明、容量不支援、log 數量不足、重複索引或非 live 標記均 fail-closed。

測試包含 5 人與 8 人的合成格式檢查，以及缺少 log、重複 index、capacity declaration mismatch、非 live、session mismatch、重複資源／entity／roster 的拒絕案例；本輪 Integration、archive、Runtime、capacity tests 為 `39 passed, 7 subtests passed`。候選 manifest 現已驗證 45 個來源。

這只準備不同容量的實測收據格式，沒有產生任何 live multiplayer 證據；目前仍只有一組帳號／客戶端，所有 production、installable、runtime 與 multiplayer flags 保持 false。
## 2026-10-10 native admission ABI recheck

重新核对保存的固定 build 只读证据：`native_admission_sites_live_20261002_r2.json` 與 `native_admission_confirmed_peer_live_20261002_r3.json` 的 capture 完整性、重讀穩定性、build `25480438`、`calls_made=false`、`writes_made=false` 均保持有效。可直接核對的 site 是 host capacity `game.dll+0x108c18f`、host allocator `+0x108c3d8`、host confirmed-peer sender `+0x108c760`、client insert `+0xb90b20` 及 player creation gate `+0x1086460`。

這些 bytes 仍不足以建立 provider：host admission table `+0x08`／`+0x50` 的實際 target 與 return ABI 未解析；client `+0xb90b20` 的 owner storage、remove/reset/reconnect 逆向路徑未閉合；`+0x1086460` 後的 resource／callback／roster partial rollback、owner lifetime、thread quiescence 與 host migration 仍未證明。現有 `confirmed_peer_external_chain_20261002.json` 明確保持 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。

因此本輪沒有把 indirect callback 猜成函式、沒有安裝 hook、沒有修改遊戲程序；現有 capacity package 仍只能作 fail-closed staging。解除阻塞需要同 build 的可驗證 callback／owner／cleanup ABI 及至少五至八個獨立客戶端實測條件。

## 2026-10-10 receive dispatch and registration replay

重新重播固定 build `25480438` 的接收边界，只读取已保存的 capture，没有启动、调用、写入或注入游戏程序。`BC2D10` 的 selector vector、`0x214C2E0` 的 592 项函数指针表、selector `168 -> BABA80 -> B90B20`、constructor 的 `owner+0xB3F8` wiring 以及六个 vector consumer 均通过静态校验；host sender 的 `0x4804FCF4` 与客户端插入函数的五字段形状也保持一致。

同时重播动态 registration caller 审计：固定 capture 中没有指向 `0x1094680` 的直接相对调用，七个静态 registration immediate 都不是 `0x4804FCF4`，该值仍只能由运行时 caller 通过 `EDX` 提供。于是 hash/event `0x4804FCF4` 到 selector `168` 的服务侧 registry、receive dispatcher 的 owner/lifetime 以及 unregister/cleanup 仍未捕获；客户端 `+0xD0` 的四笔 inline record 在 `+0x150` 与相邻结构冲突，不能安全扩展到第五至第八笔。

本轮新增可复查收据：

- `output/native_dispatch_20261010/receiver_binding_boundary_replay_20261010.json`，SHA-256 `496830a3c13d13f28e0f94c61d274a4076f4927b6ce9f4136fa81dd2fb651de1`；
- `output/native_dispatch_20261010/receive_dispatch_entry_replay_20261010.json`，SHA-256 `0ce548b3d9068553f8b118efda882959c04e404fd42ef544443fce74638b68cc`；
- `output/native_dispatch_20261010/selector_registry_replay_20261010.json`，SHA-256 `51f4346ae4469aa030702a7265fc2c8ed4c1510dc4f83c7f933d630b2cac637f`；
- `output/native_dispatch_20261010/dynamic_registration_replay_20261010.json`，SHA-256 `d7ed1ac3b4231a0ffc281483341d85e53031b1efc941b5a7f0d9bcdd8400638b`。

这些收据把“接收 vector ABI”从未知收窄为已知，但没有把运行时事件注册、角色创建、清理、房主迁移或多人功能变成已验证状态；`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 继续保持。

## 2026-10-10 live private-memory sender boundary

在官方固定版本进程 `helldivers2.exe` PID `51148`（`game.dll` 已加载，六份固定文件版本一致）上进行了一次有界、只读的私有内存扫描。扫描覆盖 128 MiB，因达到预算而截断；唯一相关命中是事件 hash `0x4804FCF4` 位于 `0x8BE3992`，没有发现 `BABA80`、`B90B20` 或 platform-member 指针命中。这个命中本身不构成注册表证据。

随后对命中页 `0x8BE3000` 做稳定双读，页 hash 两次均为 `7a1ea97c4c4fce97eb926014c8ace1189fa316d6698050b63a988c6cb49144ff`，hash 偏移固定为 `0x992`。从 `0x991` 开始的 81-byte 后缀与保存的 `game.dll+0xBE4981` sender suffix 逐字节相同，说明此私有页命中是 sender code 副本，不能被提升为 receive registry、selector、owner 或 cleanup 证据。

新增收据：

- `output/native_dispatch_20261010/live_private_registry_scan_20261010_r3.json`，SHA-256 `498a7c46bd2e747cdbebdd1567167f455337a99982a813c4b2c2948507797827`；
- `output/native_dispatch_20261010/live_hash_hit_page_replay_20261010.json`，SHA-256 `0282b4529ea1b3860c5b91da0b96899aabb6369884da35c5816d2f10cdfb13ad`。

官方程序本身能够保持运行，但本轮没有安装候选 mod、没有调用游戏函数、没有写内存、没有建立第二客户端，也没有进行入房、人数同步、离队、迁移或任务验收；所有生产和多人状态继续为 false。

## 2026-10-10 HD2Scanner live read-only admission probe

依照本機 HD2 Lua mod 工作流，新增一個獨立的只讀 diagnostic addon，使用已載入的
`_G.HD2Scanner.scan_request` 與 `HD2Scanner.api.read`。它只掃描固定 build `25480438`
的執行期指標：receiver `+0xBABA80`、client insert `+0xB90B20`、platform
consumer/state、registration/unregistration、selector dispatcher `+0xBC2D10`、
callback table `+0x214C2E0`，以及事件 hash `0x4804FCF4`；沒有呼叫任何遊戲函式，
沒有寫入記憶體，也沒有安裝 hook。

實機測試使用官方程序 PID `45352`，game base `0x7FFAFB360000`，
request `hd2_admission_probe_20261010_1`。掃描器完成約 `8305.9 MB` 可讀記憶體掃描並寫入
`DONE read_only=true no_calls=true no_writes=true`。命中如下：

- receiver pointer：3；其中兩組 context 保留 `0x7FFAFB360000` 下的 receiver 目標指標；
- selector dispatcher pointer：1；context 保留 dispatcher 目標指標；
- client insert、platform consumer/state、registration/unregistration、callback table：各 0；
- 事件 hash：18；其中一處位於 game base + `0xBE4982`，其 context 與已知 sender 程式碼 suffix 相符。

這把「執行期確實有 receiver/dispatcher 參照」從未知縮小了，但沒有證明 hash 到
receive registry/selector 的服務側映射，也沒有閉合 owner lifetime、unregister/cleanup、
client record relocation、Player Clone/resource/roster 或 host migration ABI。因此
`production_executable=false`、`installable=false`、`runtime_verified=false`、
`multiplayer_verified=false` 維持不變。探針以暫時 `9ba626afa44a3aa3.patch_128`
載入後已移除，遊戲程序也已停止。

收據與來源：

- `output/native_dispatch_20261010/hd2scanner_admission_probe_20261010.json`，SHA-256 `239964e2155bcc13dc7dcf8a2e86af81d41568f4e36ee6a8782538c24a7c5f44`；
- `output/native_dispatch_20261010/hd2scanner_admission_probe_20261010.log`，SHA-256 `c4fa041dd7e784affff7bb9922eec8e63aefca5cb5377232135f43e31953d3e6`；
- `output/native_dispatch_20261010/hd2_admission_probe_20261010.zip`，SHA-256 `5d9ae1df9f54fc4165b6beaf261a30be2a90e40a0045712f07092402b1c1f2f9`；
- source `eight_player_candidate_20260927/Package/data/mods/cainiao/hd2_admission_probe.lua`，SHA-256 `e56c8198ec25026eac3b2bc06e2006d673b7a74f72f43e46f04fb3c52c1ed5c4`。

## 2026-10-11 HD2Scanner live GameSession vtable/object probe

在固定 build `25480438` 的官方程序中，使用临时只读 addon 通过已加载的
`HD2Scanner.scan_request` 定位运行时 `GameSession` vtable。探针先按 ASLR 后的 42 个
函数指针分成 6 个不超过 64-byte 的模式，拒绝低地址副本，只接受位于当前
`helldivers2.exe` 映像范围内的完整匹配。最终唯一 vtable 为 `0x7ff6071f5b70`，
游戏模块基址为 `0x7ff605b80000`。

随后对 vtable 指针做第二轮只读扫描，约 `9031.1 MB` 可读内存中
找到 1 个对象候选 `0x1e741747e90`。对象首 qword 回读为
`0x7ff6071f5b70`，与 vtable 完全一致；扩大到 `+0x3FF` 的对象窗口中，
结构字段候选为 `+0x138` 的 dword=`1`、
`+0x13C` 的 dword=`10`、
`+0x140` 的 qword=`0x1e1a6fa29c0`。
`add_peer` 与 `remove_peer` 的运行时代码窗口都读取 `[rcx/rdi+0x138]` 和
`[rcx/rdi+0x140]`，因此这是结构上的交叉一致性；没有把这些字段命名为 peer
count、数组 owner 或可写容量。

探针还保存了 `make_host`、`shutdown_host`、`migrate_host`、`disconnect_from_host`、
`add_peer`、`peer`、`num_peers`、`remove_peer`、`leave` 九个槽位的 128-byte live
code window。与先前 live capture 的共同窗口逐位一致，但与磁盘 executable bytes
不一致，说明后续 ABI 工作必须继续以运行时 bytes 为准，不能拿磁盘内容替代。

全程记录 `read_only=true`、`no_calls=true`、`no_writes=true`；临时
`9ba626afa44a3aa3.patch_128` 已移除，游戏程序也已停止。这个结果把真实 Session
对象和关键 vtable 入口从未知缩小到可重读地址，但仍未证明调用约定、返回语义、
owner lifetime、join/leave/migration/cleanup、Player Clone 或 client replication，
所以 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 继续保持。

收据：

- `output/native_dispatch_20261010/live_session_vtable_object_probe_20261011.json`，SHA-256 `73563658bf55560722f923695c7788e0b1659eac93010e3a771cfa904da09918`；
- `output/native_dispatch_20261010/hd2_session_vtable_probe_20261011.log`，SHA-256 `e86eef94dfb9aa76c55bf4eb14d732c17b26f3216803058d38172786f0ac0f5e`；
- `output/native_dispatch_20261010/hd2_session_vtable_probe_20261011_attempts.log`，SHA-256 `7526a231f233de0661b8c1e9d667e9abddea44f2f26836ef7828e66a90e4569a`；
- `output/native_dispatch_20261010/hd2_session_vtable_probe_20261011.zip`，SHA-256 `c6b9f78515bce88fe7981f29410572d771ff92e4a0dc8e6e919935bbd6893d4d`；
- parser `five_player_feasibility_20260927/parse_hd2_session_vtable_probe_20261011.py`；测试 `test_parse_hd2_session_vtable_probe_20261011.py`。

## 2026-10-11 HD2Scanner registry-marker follow-up and vtable naming correction

先更正上一段虛表報告的名稱：`make_host`、`shutdown_host`、`migrate_host`、`disconnect_from_host`、`add_peer`、`peer`、`num_peers`、`remove_peer`、`leave` 是當時把通用 SDK 表的名稱套到內部 C++ vtable 的未證實標籤，不能當作 HD2 runtime method semantics。新的 parser 將九個入口只記為 vtable slot，`semantic_name=null`；機器碼交叉核對顯示 slot `+0x50`（RVA `0x292B60`）會建立傳輸資料並呼叫子物件，slot `+0x88`（RVA `0x292C20`）是以 opaque key 搜尋 stride `0x30` 記錄的布林判斷，slot `+0x90`（RVA `0x292CB0`）只讀取 `[rcx+0x60E4]` 後返回。這些觀察仍沒有建立 create/join/leave/migration ABI。

在固定 build `25480438` 使用 `HD2Scanner v0.8.0` 做了三次只讀 registry-marker follow-up。最新完成輪在不同 ASLR 基址下找到一個穩定的 inline data record：事件 hash `0x4804FCF4` 與 `rpc_from_host_peer_confirmed` 同一個 128-byte context 中出現，双讀相等；對該記錄起點及 hash 欄位各做 qword pointer 反查，兩個 target 的命中數都是 0。這支持「內嵌資料記錄」觀察，但不能證明 callback registry、receiver ownership、Session/Party API 或容量語義。探針仍然沒有呼叫遊戲函式、寫入記憶體或安裝 hook。

本輪 parser 只接受最新完整 run，遇到較新的未完成 run 會拒絕使用舊成功結果；新增的 parser 負變異測試確認非零 pointer reference 會 fail closed。兩份 parser 測試合計 6 tests 全部通過。`installable`、`runtime_verified`、`multiplayer_verified` 維持 false；沒有開始主機＋客戶端或 5～8 帳號任務測試。

暫時只讀 probe 的内部归档仍被放在 `F:\Game\Steam\steamapps\common\Helldivers 2\data\9ba626afa44a3aa3.patch_128`，遊戲程序已停止。這不是公開測試包，也不是容量 mod；後續須先取得真正 callback/owner/cleanup ABI，再做任何 production hook。

收據與來源：

- `output/native_dispatch_20261010/live_admission_registry_probe_20261011.json`，SHA-256 `6a8b7c103ce5f28dcf56583c1d436df5200cd930eb2bda07effb148278974516`；
- `output/native_dispatch_20261010/hd2_admission_registry_probe_20261011_r3.log`，SHA-256 `3f9d48418e56663a53f82284a48eea3a987b672361c587927576a65c7bd6e9be`；
- `output/native_dispatch_20261010/hd2_admission_registry_probe_20261011_r3.zip`，SHA-256 `8bcf93849def3008df44cb77eb5ea27932777d73d4af5f0bbf623ed8afcd1ac8`；
- `five_player_feasibility_20260927/parse_hd2_admission_registry_probe_20261011.py` 與 `test_parse_hd2_admission_registry_probe_20261011.py`；
- corrected package builder `eight_player_candidate_20260927/Package/build_hd2_admission_probe.py` 與 `build_hd2_session_vtable_probe.py`，兩者使用 `9ba626afa44a3aa3.patch_0` 归档家族。


## 2026-10-11 HD2Scanner GameSession 雙狀態 transition probe

在停止遊戲前完成固定 build `25480438` 的跨狀態只讀物件驗證：error-state receipt 記錄「連線錯誤／尚未進入飛船」狀態，最新 ship-state capture 在按下遊戲內已觀察到的 Continue 並進入飛船後完成；兩個狀態都只找到 1 個完整 vtable 指標命中，物件首 qword 都與 `0x7ff62f235b70` 完全相等。最新日誌內另有兩個完整 object scan runs。

- error-state receipt：`0x138=0`、`0x13c=0`、`0x140=0x0`、`0x148=0x2ad4ec67eb8`；
- ship-state receipt：`0x138=1`、`0x13c=10`、`0x140=0x174a04729c0`、`0x148=0x179c2c87eb8`；
- ship-state object candidate：`0x179c2c87e90`；vtable slots：42；兩輪最新日誌的 object scan runs：2；
- 兩個狀態都維持 `read_only=true`、`no_calls=true`、`no_writes=true`、`hooks_installed=false`。

這證明 `GameSession` 候選物件的結構欄位會隨遊戲狀態改變，並且不是低位址或磁碟副本誤命中；它仍然不證明 `+0x138` 是人數、`+0x13c` 是上限、`+0x140` 是 roster owner，也沒有建立任何可呼叫的 create/join/leave/migration/cleanup ABI。因此 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 維持不變，沒有開始主機＋客戶端或 5～8 帳號測試。

本輪收檔後 PID `22216` 已停止。診斷 archive 仍暫存在 `F:\Game\Steam\steamapps\common\Helldivers 2\data\9ba626afa44a3aa3.patch_128`，因先前安全審核拒絕了移除操作，保留到可用的精確安全清理路徑出現為止；它不是公開測試 mod。

收據、日誌與來源：

- `output/native_dispatch_20261010/live_session_vtable_object_probe_20261011_ship_full.json`，SHA-256 `ebf7a427240f8ab9c61c0dc058afa1c0ed37dadf89bb00ae1f9a42e92eb7d7ee`；
- `output/native_dispatch_20261010/live_session_vtable_object_probe_20261011_error_state_v2.json`，SHA-256 `b46688351ce8a9f869b3285b2b523aa7b77502c97963fa9379ee29f216560389`；
- `output/native_dispatch_20261010/hd2_session_vtable_probe_20261011_ship_full.log`，SHA-256 `61dd88c5790b1068249c54f619045183a08ca115b2464e9cce3dd87a9f643520`；
- `output/native_dispatch_20261010/hd2_session_vtable_probe_20261011_r4.zip`，SHA-256 `fededf83e181bc49638fbd424e1b9e259d624abacc21ca7e7767ef15fb4771f9`；
- parser `five_player_feasibility_20260927/parse_hd2_session_vtable_probe_20261011.py`，SHA-256 `3dbed5bd0d0543c21b2817b2d08061460c092ec9132067b114445e37e02b1795`；
- source `eight_player_candidate_20260927/Package/data/mods/cainiao/hd2_session_vtable_probe.lua`，SHA-256 `a57ad97cd73a338f50756a69ecadeed2c343a0f428316e9b74cd9b5fdcec372e`。

驗證結果：vtable parser 3/3、registry parser 3/3、archive builder 2/2 通過；本機找不到 `luajit`，所以 LuaJIT bytecode syntax check 未執行。`git diff --check` 仍會回報工作樹既有 CRLF 變更的 trailing whitespace，沒有把它擴大到本輪診斷檔案。

## 2026-10-11 HD2Scanner Party API pointer/jump-chain probe

本輪針對固定 build 25480438 的 PartyWin.dll 與遊戲內候選間接槽位做 live、只讀、
不呼叫的交叉核對。探針先確認 PartyWin.dll 的 15 個 export，包括
PartyCreateNewNetwork、PartyConnectToNetwork、PartyNetworkAuthenticateLocalUser、
PartyNetworkCreateEndpoint、PartyNetworkLeaveNetwork、PartyNetworkRemoveLocalUser、
PartyCleanup、PartyDoWork 及 state-change/configuration 相關 export。先前完整映像
pointer scan 中，create/connect/auth/endpoint 這四個主要 export 的 pointer reference 都是
0；只有 PartyNetworkLeaveNetwork、PartyNetworkRemoveLocalUser、
PartyNetworkSetCustomContext 各有 1 個 reference。這不足以證明遊戲使用哪個 export
建立或加入 lobby。

修正第一次把間接槽位套到錯誤模組基址的問題後，使用 helldivers2.exe 基址
0x7ff62dbc0000 重讀六個 EXE slot：0x13F6DB8、0x13F6EF8、0x13F6DF0、
0x13F6C30、0x13F6F70、0x13F7030。六個 target 都位於遊戲 EXE 的
.winlice 內部，沒有一個位於 PartyWin.dll。第一跳和第二跳分別為：

- create：0x7ff63083a7c8 -> 0x7ff630b83336；
- async/state：0x7ff630831173 -> 0x7ff630b8c2d5；
- authenticate/state：0x7ff630832ef2 -> 0x7ff630b0d507；
- endpoint：0x7ff630832358 -> 0x7ff630b2a2a4；
- connect：0x7ff630839d91 -> 0x7ff630b31df0；
- network auth：0x7ff63083a6c6 -> 0x7ff630b9a54e。

r6 另做了 bounded E8 byte scan；看到的 target 仍在 EXE 內部，例如
0x7ff6305391f8、0x7ff6305390d2、0x7ff63053909a、0x7ff630539206、
0x7ff6305390ee、0x7ff630539038。這個掃描可能命中 WinLicense 保護資料，
只能作為視窗收據，不能當作真實 call edge、函式語義、calling convention 或 return ABI。
全程 read_only=true、no_calls=true、no_writes=true、hooks_installed=false；
r4/r5/r6 loader 都完成載入，r6 日誌有完整 START/DONE。

實機期間外部 lobby 回傳「連線錯誤／無法進入遊戲大廳」，所以沒有 host/client、
join/leave、人數同步、host migration、cleanup 或 5～8 帳號任務驗收。這輪結果不是
公開測試 mod，也不能回答「開房即可讓 8 人進來」；目前仍沒有可安全交付的真實自定人數
mod。暫時診斷 archive 仍在
F:\Game\Steam\steamapps\common\Helldivers 2\data\9ba626afa44a3aa3.patch_128，
遊戲程序已停止。

收據與來源：

- output/native_dispatch_20261010/live_party_api_pointer_probe_20261011.json，
  SHA-256 73d1492ad1536c98be22c4d605aeaebf132c74f91da947a326c761b5208567f8；
- output/native_dispatch_20261010/hd2_party_api_probe_20261011_r6.log，
  SHA-256 1d08c566505f16cc38d75f1f651b4216b0be37947bd57eb14d61877a3af7a36f；
- output/native_dispatch_20261010/hd2_party_api_probe_20261011_r6.zip，
  SHA-256 6ac47553d08fd066a068320c14b1265a3c1628c767407b1d998f7d0f4443372d；
- source eight_player_candidate_20260927/Package/data/mods/cainiao/hd2_party_api_probe.lua，
  SHA-256 c28c7479f7b967134b5c02330b0967c8a12daeb73427bf0515c1b45382498bac；
- parser five_player_feasibility_20260927/parse_hd2_party_api_probe_20261011.py，
  SHA-256 d09b277211aa24f7fd11613ab35b3516adf58cbc7a60f0f6591d69bafedc3d7a；
- parser test five_player_feasibility_20260927/test_parse_hd2_party_api_probe_20261011.py，
  SHA-256 75943b52f1d484ce74052442347016b463f9e2e2425f382c24a3eab3c076bb47。

驗證結果：Party API parser 3/3 通過；六個 slot、兩跳視窗及 PartyWin export set 均有
固定 build 收據，但 direct_party_export_binding_proven=false、
session_party_abi_proven=false、installable=false、runtime_verified=false、
multiplayer_verified=false 維持不變。由於先前安全審核拒絕移除暫時 archive，本輪仍保留
精確路徑，沒有重試廣泛刪除。

## 2026-10-11 HD2Scanner Party/PlayFab IAT and pointer-table follow-up

r8 在固定 build 25480438 重新讀取遊戲進程的具名 IAT、六個 EXE 間接槽位及其
0x480-byte bounded table window；全程 read_only=true、no_calls=true、no_writes=true、
hooks_installed=false，capture 完成後已停止遊戲程序。

這次把 PlayFab 模組基址也納入 runtime receipt：

- game.dll base：0x7ffec2c90000；
- PartyWin.dll base：0x7fff27040000；
- PlayFabMultiplayerWin.dll base：0x7fff96f80000；
- helldivers2.exe base：0x7ff62dbc0000。

兩個具名 IAT 取得了可重讀的精確綁定：

- EXE IAT RVA 0x29617D8 的 PartyNetworkSetCustomContext target 是
  PartyWin.dll+0x1EBF0，也就是 0x7fff2705ebf0；
- EXE IAT RVA 0x29617E8 的 PFLobbySendInvite target 是
  PlayFabMultiplayerWin.dll+0x3D340，也就是 0x7fff96fbd340。

這確認遊戲運行時確實載入並使用 Party/PlayFab 層的具名函式；它沒有把
PartyCreateNewNetwork、PartyConnectToNetwork、PartyNetworkAuthenticateLocalUser 或
PartyNetworkCreateEndpoint 的 ABI 綁定出來。六個候選槽位仍全部指向 EXE/.winlice，
第一跳、第二跳及 heuristic E8 target 也都沒有落到 PartyWin。局部 table window 內
可辨認到 PartyNetworkRemoveLocalUser 與 PartyNetworkLeaveNetwork 的 PartyWin 指針，
以及其他 Party export 指針，但那些 table entries 與六個候選槽位不是同一個已證實
呼叫 ABI，不能据此猜測 create/join/auth/endpoint 參數或回傳值。

r8 的結果不是公開測試 mod，也沒有進行主機＋客戶端、離隊釋放、房主遷移或 5～8
獨立帳號任務驗收。暫時診斷 archive 仍在
F:\Game\Steam\steamapps\common\Helldivers 2\data\9ba626afa44a3aa3.patch_128。

收據與來源：

- output/native_dispatch_20261010/live_party_api_pointer_probe_20261011.json，
  SHA-256 a043207e444198ba15f28d37ca63337088c69de651ce95e3745aa83ec95d0509；
- output/native_dispatch_20261010/hd2_party_api_probe_20261011_r8.log，
  SHA-256 afb895ea1fbef1f5b4f04c27f2f61b5f0fcce44ea39b41f96cd8c9970374ba62；
- output/native_dispatch_20261010/hd2_party_api_probe_20261011_r8.zip，
  SHA-256 8b2ee7e6357ed739051bac3ee0405e7badd8b227b2e2cca3065c257acd8112a1；
- source eight_player_candidate_20260927/Package/data/mods/cainiao/hd2_party_api_probe.lua，
  SHA-256 44c74f6edcc0bcbaf39b094858722f258d46df0a876f59f07645713fa94f63d2；
- parser five_player_feasibility_20260927/parse_hd2_party_api_probe_20261011.py，
  SHA-256 b1f88f43294d20dbc1f0cbaee113326997d4795b1c9dbca473b035a925cebaa；
- tests：Party API parser 與 Session parser 合計 6/6 通過。

named_party_iat_binding_observed=true 與 named_playfab_iat_binding_observed=true 已寫入
receipt，但 direct_party_export_pointer_binding_proven=false、
session_party_abi_proven=false、installable=false、runtime_verified=false、
multiplayer_verified=false 仍保持不變。


## 2026-10-11 HD2Scanner live create/follow-on callsite windows

r9 在固定 build `25480438` 完成兩個 bounded runtime code window 的只讀擷取：`EXE+0x8E1370` 的 `create_network_callsite` 與 `EXE+0x8E1970` 的 `follow_on_callsite`，每個視窗 `0x1000` bytes。全程 `read_only=true`、`no_calls=true`、`no_writes=true`、`hooks_installed=false`；擷取完成後遊戲程序已停止，暫時診斷 archive 仍保留在
`F:\Game\Steam\steamapps\common\Helldivers 2\data\9ba626afa44a3aa3.patch_128`。

離線 Capstone 解析得到一個可重讀的交叉點：

- `create_network_callsite` 在 runtime address `0x7ff62e4a15cb` 執行 `call qword ptr [rip+0xb157e7]`，實際 slot 是 `helldivers2.exe+0x13F6DB8`；該 slot target 是先前捕獲的 `0x7ff63083a7c8`，第一跳是 `0x7ff630b83336`。
- `follow_on_callsite` 的同一 bounded window 在 `0x7ff62e4a27a0` 觀察到對相同 `EXE+0x13F6DB8` 的間接 jump；這只證明 slot reuse，不能把它命名為 PartyCreateNewNetwork 或加入流程。
- 建立呼叫前的 runtime stack config 欄位形狀為 `[input_edx, input_edx, 1, 1, 1, 0xF]`，位置是 `[rsp+0x80 .. rsp+0x94]`；`input_edx` 的本輪具體值沒有被呼叫點視窗證明為 8。
- 建立呼叫的 register/stack 形狀也已保存：`rcx=[rax]`、`rdx=rbx`、`r8=rsp+0x80`、`r9=0`、`[rsp+0x20]=rsi`，回傳後有 error/branch check。這是 ABI candidate evidence，不是已驗證的 Party export ABI。

這輪因此把「遊戲自身建立路徑確實碰到候選 slot」從靜態推測提升為固定 build 的 live code-shape evidence，但仍沒有呼叫任何未知函式，也沒有證明 create/join/leave/count/capacity/host migration/cleanup 的語義、owner lifetime、client replication 或 8 人服務端接受。`direct_party_export_pointer_binding_proven=false`、`session_party_abi_proven=false`、`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 維持不變。

收據與來源：

- `output/native_dispatch_20261010/live_party_api_pointer_probe_20261011.json`，SHA-256 `93b02673b867ffe7f18794ef7355769d62e96f160caa420cdf5aaa9c6494064f`；
- `output/native_dispatch_20261010/live_party_callsite_shape_20261011.json`，SHA-256 `6a57def1862287beb896a9110b927840020df8ac28544d9e5e263aea2d99d1d6`；
- `output/native_dispatch_20261010/hd2_party_api_probe_20261011_r9.log`，SHA-256 `5a3af9980bddcd825d21cefb09bf85406602a08facc3e583a270348f533482e1`；
- `output/native_dispatch_20261010/hd2_party_api_probe_20261011_r9.zip`，SHA-256 `e803165c1601e7ea77fb69e5ad1e8ba21639c0f152bc8df8ec59bd79aa97c4fe`；
- source `eight_player_candidate_20260927/Package/data/mods/cainiao/hd2_party_api_probe.lua`，SHA-256 `91257958c8feac04ef50cf1e73d5e8c47cd451abaeea7d935290899b9351c0f2`；
- parser `five_player_feasibility_20260927/parse_hd2_party_api_probe_20261011.py`，SHA-256 `952b05cf398e65e7b57d852120d3507e63cb89c7dc4380d4f978d4a368993540`；
- tests `five_player_feasibility_20260927/test_parse_hd2_party_api_probe_20261011.py`，SHA-256 `06dc3650c6626e44acf1527afe0b85f84d123302697e79e872327956ba562948`。

驗證結果：Party API、Session vtable、admission registry 三組 parser tests 合計 `9/9` 通過。這輪產物仍是只讀診斷 probe，不能公開測試，也不能據此宣稱「開房即可讓 8 人進來」。


## 2026-10-11 HD2Scanner PartyCreateNewNetwork ABI candidate and manager-holder follow-up

離線交叉核對固定 build `25480438` 的 r9 live create window、PartyWin.dll export prologue 與官方 Party API 參考後，建立了 ABI candidate receipt。`EXE+0x8E1370` 的呼叫點在 `0x7ff62e4a15cb` 透過 `EXE+0x13F6DB8` 間接呼叫；呼叫前的暫存器與 stack 參數位置可逐項對齊官方 `PartyManager::CreateNewNetwork`：

- `rcx`：`[rax]`，候選 PartyManager receiver；
- `rdx`：候選 `PartyLocalUser*`；
- `r8`：`[rsp+0x80]`，`PartyNetworkConfiguration*`；
- `r9d=0`：`regionCount`；
- `[rsp+0x20]` 至 `[rsp+0x40]`：regions、initial invitation、async identifier、network descriptor、applied invitation identifier。

配置欄位的 live 形狀是 `[input_edx, input_edx, 1, 1, 1, 0xF]`，順序與官方 `PartyNetworkConfiguration` 的 `maxUserCount`、`maxDeviceCount`、`maxUsersPerDeviceCount`、`maxDevicesPerUserCount`、`maxEndpointsPerDeviceCount`、`directPeerConnectivityOptions` 一致。這證明「參數形狀一致性」，仍不證明受保護 EXE target 就是 PartyWin export，也不證明本輪的 `input_edx` 實際值是 8。

呼叫點的前一個 helper `EXE+0x8E25B0` 在其 fallback 分支 `EXE+0x8E25D0` 以 `lea rax, [...]` 指向 `EXE+0x27CED10`，建立路徑緊接著執行 `mov rcx, [rax]`。因此 `EXE+0x27CED10` 被固定記錄為 manager-holder runtime read candidate；尚未成功读取其运行时值。

r11 只讀包已经加入这个 bounded qword read，并保留 r10 的候选窗口扫描代码；但当前游戏启动环境在探针写出新 `START` 之前显示 `Fatal Error`。直接启动 EXE 和 Steam `rungameid` 两种入口都复现，r9 回归也未产生新的 probe section，所以这次是启动/加载条件失败，不能当成 ABI 或多人行为证据。所有游戏进程已停止。

收据与来源：

- `output/native_dispatch_20261010/party_create_abi_candidate_20261011.json`，SHA-256 `8cd2a768415ec2139cde56e9be2b9358c814f468773c9297497e98ff3630538d`；
- `output/native_dispatch_20261010/live_party_callsite_shape_20261011.json`，SHA-256 `6a57def1862287beb896a9110b927840020df8ac28544d9e5e263aea2d99d1d6`；
- `output/native_dispatch_20261010/hd2_party_api_probe_20261011_r11.zip`，SHA-256 `8a37c5e2b10c79c50b10b6bd9f3417fe1aaaf3460e2507f032a1c749721bed83`；
- `eight_player_candidate_20260927/Package/data/mods/cainiao/hd2_party_api_probe.lua`，SHA-256 `8a968e07218c14a51362e62d02fe9aa3db3bda97a2fec0c951f56ef3064f9b18`；
- `five_player_feasibility_20260927/parse_hd2_party_api_probe_20261011.py`，SHA-256 `85278ee8374748fc61cb743154b4fcaabdc125ccb12f478762bf5f501f919fec`；
- `five_player_feasibility_20260927/test_parse_hd2_party_api_probe_20261011.py`，SHA-256 `f8e85ff89616c36b391dc91eccbeed06bac9e535682da4db53ac4383a27e42d6`。

`Party API`、`Session vtable`、`admission registry` 三組 parser tests 仍為 `9/9` 通過；`manager_holder_pointer_runtime_bound=false`、`session_party_abi_proven=false`、`installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 維持不變。


## 2026-10-11 HD2Scanner create/connect/authenticate/endpoint call-shape cross-check

利用同一個固定 build `25480438` 的 `follow_on_callsite` live window，另外保存了三個呼叫點的 ABI candidate：

- `connect_network_candidate`：runtime `0x7ff62e4a19ac`，slot `EXE+0x13F6F70`。`rcx=[rax]`、`rdx=rbx`、`r8=rdi`、`r9=[rdi+0x80]`，與官方 `PartyManager::ConnectToNetwork(networkDescriptor, asyncIdentifier, network**)` 的 receiver、descriptor、async context、output pointer 位置一致。
- `auth_network_candidate`：runtime `0x7ff62e4a1a0e`，slot `EXE+0x13F7030`。`rcx=[rdi+0x80]`、`rdx=[rdi+0x88]`、`r8=rsi`、`r9=0`，與官方 `PartyNetwork::AuthenticateLocalUser(localUser, invitationIdentifier, asyncIdentifier)` 的 network receiver、local user、invitation string、async context 位置一致。
- `create_endpoint_candidate`：runtime `0x7ff62e4a1ad8`，slot `EXE+0x13F6C30`。`rcx=[rdi+0x80]`、`rdx=[rdi+0x88]`、`r8d=0`、`r9=0`、`[rsp+0x20]=rsi`、`[rsp+0x28]=rdi`、`[rsp+0x30]=&rdi+0x90`，與官方 `PartyNetwork::CreateEndpoint(localUser, propertyCount, keys, values, asyncIdentifier, localEndpoint**)` 的零 property 配置一致。

這使 create、connect、authenticate、endpoint 四條路徑都有固定 build 的參數形狀證據；仍沒有把四個受保護 EXE slot target 绑定到 PartyWin export，也没有读取 manager/local user/network/invitation 实际指针，更没有调用它们。`LeaveNetwork` 在先前 bounded table 中可辨认到 PartyWin export pointer，但 leave/cleanup 的 owner、回调和状态改变生命周期仍未闭合。

官方参考：

- `CreateNewNetwork`：https://learn.microsoft.com/en-us/gaming/playfab/multiplayer/networking/reference/classes/partymanager/methods/partymanager_createnewnetwork；
- `ConnectToNetwork`：https://learn.microsoft.com/th-th/xbox/playfab/multiplayer/networking/reference/classes/partymanager/methods/partymanager_connecttonetwork；
- `AuthenticateLocalUser`：https://learn.microsoft.com/en-us/gaming/playfab/multiplayer/networking/reference/classes/partynetwork/methods/partynetwork_authenticatelocaluser；
- `CreateEndpoint`：https://learn.microsoft.com/es-es/gaming/playfab/multiplayer/networking/reference/classes/partynetwork/methods/partynetwork_createendpoint。

收据：`output/native_dispatch_20261010/party_session_abi_candidates_20261011.json`，SHA-256 `140800dd343b2f3116322f8bc37cf267e83c813807a8ca6a0e2c5db38b05fe3b`。四个 shape 都标记为 `true`，但 `candidate_targets_bound_to_partywin_exports=false`、`return_abi_runtime_verified=false`、`host_client_tested=false`、`multiplayer_verified=false` 维持不变。


## 2026-10-11 HD2Scanner external read-only manager-holder cross-check

因当前 addon loader 没有产生新的 `START`，在游戏进程短暂处于 `Fatal Error`/启动前状态时做了一个等价边界的外部只读交叉核对。使用 `ReadProcessMemory` 读取固定 build `25480438` 的模块基址、`EXE+0x27CED10`、四个 candidate slot 以及两个 live callsite window；没有调用函数、没有写入、没有 hook。

结果：

- `helldivers2.exe` base：`0x7ff62dbc0000`；
- `EXE+0x13F6DB8` -> `0x7ff63083a7c8`；
- `EXE+0x13F6F70` -> `0x7ff630839d91`；
- `EXE+0x13F7030` -> `0x7ff63083a6c6`；
- `EXE+0x13F6C30` -> `0x7ff630832358`；
- `EXE+0x27CED10` 的 qword 是 `0x0`。

四个 slot 与 r9 的 live receipt 一致，说明这些 slot 仍可从外部只读路径重读。holder 为零只说明本次进程还没有完成可用的游戏初始化，不能说明它在完整 ship/menu 状态永远为空，也不能作为 PartyManager 生命周期结论。为了绑定真实 receiver，仍需一次不在 Fatal Error 状态的完整游戏运行时读取。

receipt：`output/native_dispatch_20261010/live_party_manager_holder_external_read_20261011.json`，SHA-256 `7f47cd5cc6043a8257af4921d6d7ad9e77975852a15173b8c00443c8b02a5ff8`。读取完成后进程已停止。


## 2026-10-11 HD2Scanner parser verification update

Party API parser 新增 holder、4KB hop window 與 RIP indirect record 的欄位驗證；Party API、Session vtable、admission registry 三組 tests 目前合計 `10/10` 通過。這些測試只驗證收據解析與 fail-closed 條件，不把 synthetic fixture 當成 multiplayer 成功。


## 2026-10-11 HD2Scanner Party/Session lifecycle gap matrix

已把原始目标的八个实际要求逐项映射到当前证据：create、join、leave、人数同步、容量校验、房主迁移、cleanup、任务实例一致性。四个调用点目前只有固定 build 的参数形状候选；leave/cleanup 只有 export 或 bounded table pointer；没有一项拿到完整 owner、return、state-change、replication 和跨客户端行为闭环。

矩阵：`output/native_dispatch_20261010/party_session_lifecycle_gap_matrix_20261011.json`，SHA-256 `15251b3257e2971feb1ba1e842836745dfca80f9204b8b4a20957819fb5dcfba`。公开发布、runtime verified、multiplayer verified 全部维持 false。


## 2026-10-11 HD2Scanner startup baseline isolation and capacity staging package

為分離診斷包與啟動環境，先以已知可產生 r9 probe 收據的包重試 Steam `-applaunch 553850`，再清空 `LaunchOptions` 後以 `--bundle-dir data --release` 觀察，最後暫時移開 `patch_128` 做無診斷包基線。r9 與 clean launch 都在新的 loader `START` 前進入 `Fatal Error`；無診斷包基線在 15 秒內沒有留下遊戲程序。測試後已恢復 `data/9ba626afa44a3aa3.patch_128`，沒有刪除檔案、沒有呼叫 native 函式、沒有寫入遊戲記憶體，也沒有把結果當成 ABI 或多人證據。

收據：`output/native_dispatch_20261010/live_startup_baseline_isolation_20261011.json`，SHA-256 `476a98a3b05d74416d02c157d81ed8116c189c5dd5a810729705f605695e9f46`；STATE SHA-256 `bdb767bec86ac93d133e044e133211ac57a79c774e9f8a7cfd52441ece572b32`。

同時生成自定人數 staging 包 `output/native_dispatch_20261010/HD2-Player-Capacity-staging-0.15.0.zip`，SHA-256 `0d247c9c199fb89587283acab6f76b54db0a7f12098fc5e0ab4c96f8f2a080f4`。它包含 4/5/8/12/16 選項與 fail-closed native control boundary；`provider_bound=false`、`multiplayer_verified=false`，只能用來測試選單與拒絕流程，不能宣稱開房可容納八人。


## 2026-10-11 HD2Scanner explicit GameGuard startup blocker

以已恢復的 Steam 配置和曾成功產生 r9 probe 的 `steam://run/553850` 入口重試後，游戏命令列为 `--bundle-dir data --release +connect_lobby -212`，但窗口仍为 `Fatal Error!`。Steam `gameprocess_log.txt` 随后记录 `GameGuard\ggerror.des`，系统启动 Edge 打开 `https://gameguardfaq.nprotect.com/cn/con_01.html`。loader、HD2Scanner 和 Party probe 都没有新的 `START`，所以这不是 Session/Party 行为，也不能用来推导八人结果。游戏进程已停止，所有 native calls、memory writes 与 hooks 继续关闭。

收据：`output/native_dispatch_20261010/live_gameguard_startup_block_20261011.json`，SHA-256 `9c4066114dd665483f5efafb590ab2f0bb08f9a7db9402d90cd479409e638787`；STATE SHA-256 `030c03d25e04f65770196b735ad1883e11a2ba6b363986a4469ae008ee6b63d6`。


## 2026-10-11 correction: loader package format and invalid baseline

重新核对 `data/9ba626afa44a3aa3.patch_128` 后确认它与 r9 ZIP 完全相同，外层是 loader 使用的 ZIP，内部才包含 `Addon/9ba626afa44a3aa3.patch_0`。先前把内部 patch 单独安装的推论已撤回；提取目录只用于检查，没有安装。另一个“无诊断包基线”发生在 Steam `AppError_16 / WaitingPrevProcess` 状态，游戏进程没有创建，因此该基线不再作为启动环境或包格式证据。

格式收据：`output/native_dispatch_20261010/hd2_loader_package_format_crosscheck_20261011.json`，SHA-256 `746dae7742d1f2e06fdb3f79b204c287f52727fb387be49296ae9e6d96e8a56e`。修正后的启动收据：`output/native_dispatch_20261010/live_startup_baseline_isolation_20261011.json`，SHA-256 `042588a6c77482aabcfa8a63d35c4b3958db17c5e1093ce5ccfc8318918e237e`。

## 2026-10-15 Party manager 的 handle 與物件關聯

本輪仍跳過多人驗證，沒有開啟遊戲程序、載入插件或修改遊戲檔案。磁碟 EXE 與 PartyWin 指紋仍符合固定版本。上一輪對 `.winlice` 區段使用 `get_offset_from_rva` 得到的檔案位元組不能作為程式碼證據：該區段沒有 raw data；新分析入口明確拒絕沒有檔案資料的 RVA。

官方 [PartyImpl.h](https://github.com/PlayFab/PlayFabParty/blob/master/include/PartyImpl.h) 顯示 C++ `PartyManager` 保存獨立的 `_handle`；[Party_c.h](https://github.com/PlayFab/PlayFabParty/blob/master/include/Party_c.h) 的 C exports 接收 opaque handle。兩者不是同一個物件位址。`GetNetworkConfiguration` 輸出是 `const PARTY_NETWORK_CONFIGURATION**`，`GetNetworkDescriptor` 則是 `PARTY_NETWORK_DESCRIPTOR*`，原始分析工具已更正。

固定版本 PartyWin 的 `0x158F8` 呼叫 `0x26860` resolver；後者在 `0x26921` 讀取 `PartyWin+0x3B6460` 的 manager 物件。tagged handle 分支呼叫 `0x26DB0`，讀物件 `+0x600`，在 `0x26968` 與輸入 handle 比較。三段程式碼與指令 operand 已核對。既有 PID38492 快照的遊戲 holder 是 `0x111D43778D00F0C2`，符合此分支的低位元形狀；不能把它直接當成普通指標，也不能憑此宣布有效。

`tools/party_manager_binding.py` 已實作只讀關聯觀察，並接入既有 `capture_live_party_slots_20261111.py`。先驗證 EXE/game/PartyWin identity 與 code pins，再讀遊戲 holder、PartyWin manager global、manager+0x600 並復讀；新增資料最多 48 bytes，全工具上限 64 KiB。只跟隨經固定位置取得的 manager 物件指標，不解參照 opaque handle。結果即使相等仍保留 `runtime_provider_ready=false`、`target_binding_proven=false`、`owner_lifetime_proven=false`。

離線範圍檔：`output/native_dispatch_20261010/party_manager_capture_plan_20261015.json`。修正後靜態 ABI：`output/native_dispatch_20261010/partywin_c_handle_abi_20261015.json`。使用者隨後明確答覆「暂时继续离线，不读取游戏」；上述單次 manager 擷取未獲授權，沒有執行，也不再視為等待答覆。後續僅處理工作區原始碼與既有資料，不啟動、檢查或讀取遊戲程序，不重複提出同一擷取要求。

依此範圍繼續檢查後，修正了舊 `parse_hd2_party_api_probe_20261011.py` 的 holder 語義：保留歷史紀錄的地址範圍旗標，但明確標示該數值為 opaque handle，不將旗標或 target-code hash 當作 manager 物件綁定證據。對固定 holder 核對 EXE base/RVA、8-byte raw 與記錄值是否一致；區分未讀到、讀到零與非零 handle。任何成功解析仍不宣告 manager object binding 或 runtime verified。

針對這次修改執行 parser tests，結果 `7 passed, 7 subtests passed`。新增案例覆蓋保存的 PID38492 非指標 handle 值、零與 nil 的區別，以及地址、長度或數值不一致；這些案例是離線 fixture。重播保存的 r9 原始日誌後，原採樣 metadata、IAT、六個間接槽、呼叫點、export 與 production flags 均與舊收據相同；r9 沒有 holder 記錄，不補造該欄位。原始日誌與歷史收據未修改。

目前檢查的 r13 與 PID38492 資料保留了遊戲端 handle，但沒有 PartyWin manager global 及 manager+0x600 的對應值，無法在離線資料中證明此關聯。已核對 `ep_bridge_admit_at` 的固定 index 檢查仍在，無須重做已完成的修正。受保護呼叫槽的目標、實際遊戲 admission/creation provider、多客戶端同步與 5–8 人驗收仍未完成；這次沒有新增可玩八人的 Mod 包。

## 2026-10-15 新對話：保存呼叫鏈的六個位置基址 helper

新對話已實際建立並讀回 `完成HD2多人上限mod` 目標，狀態為 `active`、沒有 token 預算。授權繼續限定為工作區原始碼與既存資料；本輪沒有存取遊戲程序或安裝目錄。

針對 `live_party_jump_chains_20261111_pid38492_r5.json` 中六個先前稱為 dispatcher target 的入口，核對來源 SHA-256 `dd41ee4dd10021cb2b5e91bba9702d2e5abb5b98698f6bc717017b41d8ea5254` 及各 helper 視窗雜湊後，逐 byte 確認六個完整 14-byte body 均為 `call next_instruction; pop rbp; sub rbp, immediate; ret`。入口 RVA 分別為 `0x29791F8 / 0x29790D2 / 0x297909A / 0x2979206 / 0x29790EE / 0x2979038`；各自的 next-IP 減 immediate 都得到 `EXE+0x2979000`。

這六個 helper 的功能是設定共同位置基址後返回，body 本身沒有 PartyWin 呼叫，不能當作已找出的 Party dispatcher。外層各 256-byte 視窗在後續控制流程完整呈現前截斷；只掃 helper 後面的鄰接 bytes 是否有 import call，無法補出外層真正目標。已檢查的 r13 JSON 雖列出 4096-byte 視窗，但僅保存 hash 與前綴，不包含完整視窗 bytes，因此不能用這份收據重建缺少的指令。這是保存資料的靜態指令推導，沒有執行 helper，也不是執行或多人驗證。

本輪原始碼搜尋仍顯示 `ep_control_bind`、`ep_pcr_init`、`ep_replication_bridge_init` 的實際呼叫只在測試程式，沒有新增正式 provider。原始快照與歷史收據保持原樣，沒有重跑既有通過套件或重新產包。`installable/runtime_verified/multiplayer_verified/public_release_allowed=false`、`max_verified_players=4` 維持不變。後續只有取得目前工作區尚未定位的完整已保存 wrapper bytes，或日後條件與授權改變，才可能沿這條路繼續接入；不得把新對話或上述 helper 識別當成缺口已解除。

## 2026-10-15 歷史工具輸出找回六個完整視窗

後續在較早聊天 `01a12480-a6ee-7db2-b2a9-00f6c07f2919` 的保存 JSONL 第 9842 行及相關重複輸出，找回六段完整 `HOP_WINDOW`，共 24,576 bytes。每段地址、label、depth 與完整 SHA-256 均符合原 r13 收據；其中包含 `authenticate_or_state_candidate`、`connect_network_candidate`、`auth_network_candidate` 三個 depth-1 外層視窗。這補回了上一節尚未定位的部分 bytes，並不改變原 r13 JSON 本身只有 hash／前綴的事實。另六個視窗尚未找回。原歷史記錄、r13 收據與 r5 快照沒有修改，也沒有讀取 AppData 遊戲日誌或遊戲程序。

原始 bytes 與來源行雜湊保存在 `output/native_dispatch_20261010/recovered_party_windows_20261015/`；`manifest.json` 明列來源、對照收據與未找回的視窗。新增 `five_player_feasibility_20260927/tools/replay_recovered_party_prefixes_20261015.py` 使用專案既有 Unicorn 依賴，僅在隔離記憶體執行保存的 prefix 與已核對的 14-byte helper，遇到第一筆沒有資料的讀取立即停止，不補造資料、不接入遊戲。

三條 prefix 的獨立 32-bit 常數計算與原始指令重播結果一致：

| 候選標籤（仍未證實 API 名稱） | 第一個資料讀取指令 RVA | 讀取位置 RVA | 大小 |
| --- | --- | --- | --- |
| authenticate_or_state_candidate | `0x2F4D5B7` | `0x29848A7` | 8 bytes |
| connect_network_candidate | `0x2F71E88` | `0x2984C3F` | 8 bytes |
| auth_network_candidate | `0x2FDA5D6` | `0x298568F` | 8 bytes |

r13 記錄的 22 個 hop、callsite 與 helper 程式碼範圍都不涵蓋這三筆讀取。因此重播停在此處；未讀取值不能用零或猜測指標代替。保存的 `prefix_analysis.json` 明列這只是初始暫存器／stack 為合成狀態的離線 prefix 分析，不是完整 wrapper、實際呼叫結果、provider 綁定或多人驗證。

本輪取得的是可繼續分析的原始程式碼及具體資料依賴，沒有新增可安裝八人 Mod；四項發布／實機門檻與 `max_verified_players=4` 維持原值。下一步只沿這三個固定資料位置追查已保存內容；不得因此啟動或讀取遊戲，也不重複要求已被拒絕的擷取。

恢復活動後補做連線候選路徑的靜態資料流核對：`EXE+0x2984C3F` 的未知 qword 並非無效讀取。設其值為 `x`，在 `EXE+0x2F720A9` 的間接呼叫前，`RAX` 低 32 位元為 `u32(u32(x)-0x38C38943) XOR 0x5FA365AE`，高 32 位元為 `u32(x>>32) XOR 0x86A1AF6E`。兩半皆為可逆運算，未知值的全部位元均保留，不能忽略或以零代替。該呼叫 operand 是 `[rbp+0x2FCFEC]`，此處 `RBP=EXE base+0x2979000`，對應槽位 `EXE+0x2C75FEC`；槽位值與呼叫語義仍未證實，不能把計算出的 `RAX` 命名為 Party 函式指標。此核對只使用已找回且 SHA-256 固定的 connect 視窗、stack 資料流與 32-bit 常數折疊，沒有補造讀值、呼叫未知函式或重新執行既有套件。

## 2026-10-15 從保存的原始日誌補齊十二個視窗

沿既有歷史來源定位到 `C:\Users\OvO\AppData\Local\CowboyBingus\Helldivers2\Logs\HD2PartyApiProbe.log`，檔案最後寫入時間為 `2026-10-11T10:12:55.810075Z`。本輪只讀取這份已保存日誌，沒有啟動、查詢或讀取遊戲程序。檔案讀取前後大小及修改時間一致；整檔 289,963 bytes 的 SHA-256 為 `9b808271d099d882ea61eede167ff5265bf457aa7ed683f8b4aae328e811823b`，與舊 `runtime_callsite_slot_audit_20261111.json` 一致。其前 289,888 bytes 的 SHA-256 恰為 r13 原始日誌指紋 `3e7d9ffa6a9ec40d45c1d9e746f69aa34b1bea7cc3527bb0dda32a396e8559bd`，已另存為 `recovered_party_windows_20261015/source_probe_r13_exact.log`；整檔保存為同目錄的 `source_probe.log`，原檔未修改。

r13 的十二個 4 KiB 視窗現已全部找回，共 49,152 bytes；每段地址與 SHA-256 均對上原收據。補齊 `create_network_candidate`、`async_or_state_candidate`、`create_endpoint_candidate` 三個外層視窗後，既有重播工具擴充到六條 prefix。新增三條的首筆未知讀取分別為 `EXE+0x2985447`、`EXE+0x2985527`、`EXE+0x2984B7F`，均為 8 bytes；原始指令重播結果與獨立 32-bit 常數折疊一致。全部六條仍在首筆未保存資料處停止，不提供替代值。這是歷史資料恢復與離線指令分析，沒有新增遊戲擷取或實際函式呼叫。

完整舊日誌沒有補出六個 entry qword、`EXE+0x2C75FEC` 的槽位值或 PartyWin manager 關聯。六條路徑的名稱仍只是候選標籤；固定長度視窗不是完整函式或實機成功證據。`STATE.json` 已更新恢復數量、來源、工具與分析雜湊，原始 r13 收據及 r5 快照保持原樣。真實 admission/creation/replication provider 與八人驗收仍未完成，所有發布／實機門檻維持 false。

## 2026-10-15 採樣工具 v2：僅離線完成，等待明確授權

使用者授權「先离线补齐采样工具，加入新增读取项和64 KiB上限」，並明確要求不啟動、檢查或讀取遊戲。本輪只修改工作區採樣工具、加入假讀取器測試、讀取工作區已保存的歷史 bytes 並產生離線清單；沒有列舉遊戲程序、檢查安裝版本、讀遊戲檔案／日誌或執行實機採樣。

工具：`five_player_feasibility_20260927/tools/capture_live_party_slots_20261111.py`。最終機器可讀清單：`output/native_dispatch_20261010/party_capture_plan_v2_20261015.json`，包含每個固定 RVA、長度、次數、程式碼指紋與條件讀取規則。舊 v1 清單和歷史收據保留，後續使用 v2 清單。

以下 EXE 均指授權採樣當次驗證的 `helldivers2.exe` 基址，不能重用歷史絕對位址。名稱仍是候選標籤，不代表已確認的 API。

| 候選 | 新資料 RVA（8 bytes × 2） | wrapper RVA（1024 bytes × 2） | 位置 helper RVA（14 bytes × 2） | 原槽 RVA（8 bytes × 2） |
| --- | --- | --- | --- | --- |
| create_network | `0x2985447` | `0x2FC3336` | `0x29791F8` | `0x13F6DB8` |
| async_or_state | `0x2985527` | `0x2FCC2D5` | `0x29790D2` | `0x13F6EF8` |
| authenticate_or_state | `0x29848A7` | `0x2F4D507` | `0x297909A` | `0x13F6DF0` |
| create_endpoint | `0x2984B7F` | `0x2F6A2A4` | `0x2979206` | `0x13F6C30` |
| connect_network | `0x2984C3F` | `0x2F71DF0` | `0x29790EE` | `0x13F6F70` |
| auth_network | `0x298568F` | `0x2FDA54E` | `0x2979038` | `0x13F7030` |

其餘固定／條件讀取：

| 位置 | 單次長度 × 最多次數 | 用途／條件 |
| --- | --- | --- |
| EXE + `0x2C75FEC` | 8 × 2 | 共同間接呼叫槽 |
| EXE + `0x27CED10` | 8 × 2 | opaque handle，只記錄值，不解參照 |
| PartyWin + `0x3B6460` | 8 × 2 | manager 物件指標 |
| 該 manager 物件 + `0x600` | 8 × 2 | 僅在物件指標地址有效時讀 stored handle |
| EXE、game.dll、PartyWin.dll 三個 PE header | 每個 4096 × 2 | 採樣前後核對載入映像 identity |
| game.dll + `0x108C18F`、`0x4EDAA4` | 分別 76 × 2、36 × 2 | 固定程式碼指紋 |
| EXE + `0x8E25B0` | 91 × 2，另有 1280 × 1 | manager helper 指紋及保留的原始 helper 視窗 |
| PartyWin + `0x15720`、`0x26860`、`0x26DB0` | 分別 960 × 2、496 × 2、188 × 2 | manager layout 程式碼指紋 |
| EXE + `0x8E1370`、`0x8E1970` | 每個 1024 × 1 | 保留的原始呼叫點視窗 |
| 六個原槽指向的程式碼 | 每個最多 512 × 1 | 整個範圍必須位於已驗證 EXE |
| 共同呼叫槽指向的程式碼 | 最多 512 × 1 | 整個範圍必須位於三個已驗證模組之一 |

新缺失資料加 manager 關聯共 80 個不重複 bytes，含復讀最多 160 bytes。全部固定讀取含復讀為 44,294 bytes，條件讀取最多 3,600 bytes，完整清單最大 **47,894 bytes**。工具本身另設不可由命令列放寬的 **65,536 bytes（64 KiB）** 上限，所有驗證、復讀和失敗請求都先按請求長度計數，超限不交給底層讀取器。共同槽及原槽的目標視窗要求可執行的 MEM_IMAGE，跨模組邊界或位於未驗證模組／私有記憶體者只記錄目標值及已知模組歸屬，不讀目標 bytes；不沿跳轉或解碼結果繼續追蹤。

64 KiB 指進程記憶體內容請求，不包含 OS metadata 查詢和磁碟檔案雜湊。未來授權時會對指定 PID 查詢 EXE 路徑、已載入模組名稱／路徑／基址／大小，以及所讀範圍的保護屬性；只讀三個載入映像對應的磁碟檔案完整內容以核對 SHA-256（固定 build 25480438，完整指紋見 v2 JSON）。不搜尋其他 PID，不掃描整個遊戲目錄，不讀日誌、存檔或其他遊戲檔案。版本或指紋不符、讀取被拒／不足、預算用盡或關鍵值復讀變化即停止，不自動重試或提權。

離線驗證：`test_capture_live_party_slots.py` 與既有 `test_party_manager_binding.py` 合計 **45 passed**，XML 收據為 `output/native_dispatch_20261010/party_capture_offline_tests_20261015.xml`。測試用假後端逐筆核對地址、長度與次數；檢查新欄位復讀、原始 handle 不被當作指標、目標模組完整範圍、初始／結束程式碼指紋、64 KiB 邊界、失敗請求計數、不覆寫輸出及停止時關閉假 handle。測試不建立真實 WindowsReader；三個磁碟映像驗證入口皆被替換成假資料或禁止存取。工具的真實讀取成功與否尚未驗證。

以後執行只需一台電腦、一個帳號，不需要組隊。步驟如下，**本輪沒有執行第 2–4 步**：

1. 使用者先明確授權按本 v2 清單進行一次只讀採樣（含上述三個檔案指紋、metadata 與記憶體範圍）。在授權前保持不啟動、檢查或讀取遊戲。
2. 使用者正常手動啟動遊戲，進入自己單人的穩定飛船狀態，不進任務；用工作管理員「詳細資料」提供 `helldivers2.exe` 當前 PID，並告知已在單人飛船。不要提供舊 PID。
3. 對這一個 PID 執行一次工具，指定全新的工作區輸出檔；用實際 PID 替換下面佔位文字。工具不安裝插件、不呼叫遊戲函式、不寫記憶體、不安裝 hook、不修改遊戲檔案。

```powershell
py -3.12 "E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\tools\capture_live_party_slots_20261111.py" --pid <當前PID> --output "E:\File\Codes\0\26.10.1\HD2\output\native_dispatch_20261010\party_capture_authorized_01.json"
```

4. 工具成功或停止都關閉 handle；成功寫 v2 收據，預期讀取錯誤寫 `status=stopped`、原因、已請求 bytes 和逐筆紀錄。已存在的輸出檔在打開進程前拒絕覆寫。停止後不擴大範圍／換後端重讀；僅分析保存收據，再報告缺口。

採樣只能補資料依賴與觀察到的 manager 關係，並不證明 ABI、owner lifetime、provider 可用或八人遊玩。`installable`、`runtime_verified`、`multiplayer_verified`、`public_release_allowed` 仍為 false，`max_verified_players=4`。最終採樣授權尚未取得。

## 2026-10-16 已授權的單次 v2 採樣完成：PID 30776

使用者先明確授權 v2 單次只讀採樣，之後回報已在穩定單人飛船並提供 PID 30776。本次只執行一次既有 v2 工具，沒有啟動遊戲、搜尋其他 PID、重試、擴大範圍、呼叫遊戲函式、寫入記憶體或安裝 hook。工具於台北時間 `2026-10-16 20:53:34 +08:00` 產生成功收據後關閉 handle。這次授權已用完，剩餘擷取次數為 0；後續只分析工作區保存資料，不把此授權延伸為持續讀取或跳轉追蹤。

原始收據：`output/native_dispatch_20261010/party_capture_authorized_20261016_pid30776_01.json`，SHA-256 `b5b81a890e9a0e81808bcd74a736a75ac48f59de33cf393f135ef9c5478d13ac`。離線核對：`output/native_dispatch_20261010/party_capture_analysis_20261016_pid30776_01.json`，SHA-256 `e8913e2285129c687dd875aaceab9f50232fbfadeda14ca5f17466cf7ca315cd`。

三個磁碟映像的完整指紋符合 v2 固定版本；載入頭及固定程式碼的前後校驗均通過。84 筆記憶體讀取全部成功，共 **47,894 bytes**，低於 **65,536 bytes** 硬上限。離線逐筆比對確認地址、長度和次數完全符合 v2 清單；初始校驗 20,363 bytes、資料 256 bytes、程式碼視窗 6,912 bytes、結束校驗 20,363 bytes。六個入口資料、六個原槽、共同槽與三個 manager 欄位，共 16 個 qword 的復讀均一致。完整檔案雜湊與 OS metadata 依既定清單不計入記憶體內容上限。

本次取得的六個入口值：

| 候選 | EXE RVA | 64-bit 值 |
| --- | --- | --- |
| create_network | `0x2985447` | `0xE8C31F18A7EB3AFF` |
| async_or_state | `0x2985527` | `0xC93C09417BE6817C` |
| authenticate_or_state | `0x29848A7` | `0xB7AA506089A70337` |
| create_endpoint | `0x2984B7F` | `0xED6502BB5A359C2E` |
| connect_network | `0x2984C3F` | `0x86A1D09257E2B391` |
| auth_network | `0x298568F` | `0xF8C350E96FAE72DF` |

遊戲端 handle 與 manager 物件保存的 handle 均為 `0x18C30CA1FE92B322`；PartyWin manager 物件為 `0x218C7012AF0`，其 `+0x600` 欄位已依清單讀取及復讀。觀察結果為 `manager_handle_relationship_observed`；沒有解參照 opaque handle。這是當次資料關係，不保證原子快照或物件生命週期。

共同槽 `EXE+0x2C75FEC` 指向 `EXE+0x2C7A94D`。保存的 512-byte 前綴第一條指令是直接跳轉至 `EXE+0x2EFAF2D`；該目的地不在本次讀取範圍，沒有追讀。入口第一條跳轉後面的線性 bytes 不當作實際執行路徑。

把新 connect qword 代入先前已保存的 wrapper 公式，得到呼叫共同槽前的推導值 `RAX=0x7FFC40BC4FE0`，即當次已驗證的 `PartyWin.dll+0x14FE0`。此 RVA 與同一 PartyWin 指紋下已保存的 `PartyConnectToNetwork` export 相符。這補上「入口資料可解碼至命名 export 地址」的證據；共同 dispatcher 如何使用該值、完整參數／回傳 ABI、服務端接受及 5–8 人行為仍未驗證，不能把地址匹配記成已呼叫成功。

下一步可對新保存值與既有 wrapper bytes 做離線分析，先確認其他五條入口的資料流及工作區是否已有共同跳轉目的地的保存 bytes。`provider_binding_proven`、`installable`、`runtime_verified`、`multiplayer_verified`、`public_release_allowed` 維持 false，`max_verified_players=4`。本次沒有多人遊玩驗收或新增可玩八人包。

## 2026-10-16 六個入口值的離線解碼

新增 `five_player_feasibility_20260927/tools/decode_captured_party_entries_20261016.py`，只讀工作區保存的 PID30776 收據、v2 清單、r5/r13 歷史收據、十二視窗 manifest 與靜態 ABI 記錄。所有來源固定 SHA-256；歷史 wrapper 的前 1024 bytes 與 14-byte helper 均須對上 PID30776 採樣前後的程式碼指紋，才可用於該次資料的離線計算。沒有重新讀取遊戲或安裝目錄。

工具在 Unicorn 隔離記憶體內重播各 wrapper，僅供應本次實際取得的對應入口 qword，並使用三組不同的合成暫存器、stack 及旗標。讀取未提供的資料或映射頁面的空白填補、執行未保存的指令、出現額外呼叫或寫入合成 stack 以外的區域，均停止。每條路徑只有一筆非 stack 資料讀取，即原先缺失的 8-byte entry；所有路徑都在 `call qword ptr [rbp+0x2FCFEC]` **執行之前**停止，不執行共同 dispatcher 或 Party 函式。

| 原候選標籤 | 停止的 EXE 呼叫點 RVA | 推導的 PartyWin RVA | 保存資料可確認的名稱 |
| --- | --- | --- | --- |
| create_network_candidate | `0x2FC3552` | `0x15720` | `PartyCreateNewNetwork` |
| async_or_state_candidate | `0x2FCC515` | `0x19880` | 未命名，不依候選標籤推斷用途 |
| authenticate_or_state_candidate | `0x2F4D788` | `0x1BE80` | 未命名，不依候選標籤推斷用途 |
| create_endpoint_candidate | `0x2F6A506` | `0x1C050` | `PartyNetworkCreateEndpoint` |
| connect_network_candidate | `0x2F720A9` | `0x14FE0` | `PartyConnectToNetwork` |
| auth_network_candidate | `0x2FDA79D` | `0x1BC80` | `PartyNetworkAuthenticateLocalUser` |

三組合成初值對每條路徑皆得到相同目標與指令路徑，connect 的結果也與先前獨立常數公式一致。這是保存資料的解碼結果及有限合成初值核對，不是實際呼叫暫存器快照，也沒有證明所有可能初值或完整參數／回傳 ABI。

共同入口 `EXE+0x2C7A94D` 的第一條跳轉，同時存在於舊 `create_network_candidate_d0.bin` 和本次 512-byte 前綴，五個指令 bytes 完全相同，目的地仍是 `EXE+0x2EFAF2D`。已核對的十二個完整歷史視窗和本次採樣均未涵蓋該目的地；在保存的 r13 export 清單與靜態 ABI 記錄內也沒有 `0x19880`、`0x1BE80` 的名稱。此搜尋結論只涵蓋上述來源，不把缺失資料以零或猜測實作補上。

結果：`output/native_dispatch_20261010/party_entry_decode_20261016.json`。針對新工具的測試為 `test_decode_captured_party_entries.py`，**11 項斷言通過、退出碼 0**；XML 保存於 `output/native_dispatch_20261010/party_entry_decode_offline_tests_20261016.xml`。pytest 執行期間 Unicorn `mem_map` 輸出了 Windows access-violation 原生診斷，程序最後正常完成；這項現象已記入 STATE，不能把測試退出碼視為原生或遊戲穩定性驗證。直接執行離線分析工具產生報告成功。

本輪把六個未知 entry 的去向縮小為六個固定 PartyWin RVA，其中四個可命名。共同 dispatcher 語義、另兩個 RVA 的名稱、完整呼叫契約和真正多人加入／生成／同步仍未完成。所有實機／發布門檻保持 false，單次採樣授權剩餘次數仍為 0。

## 2026-10-16 共同呼叫邊界：不能以簡單 JMP RAX 替代

沿前輪解碼工具增加對呼叫邊界的觀察，使用彼此不同的合成 caller return marker 與第 5–9 個 stack 參數 marker，避免原先均勻填充的 stack 隱藏參數錯位。仍在共同間接呼叫前停止，不提供假 dispatcher、不模擬 Party 函式回傳，不存取遊戲。

六條路徑各三組合成初值，共 18 組結果都保留 `RCX/RDX/R8/R9` 的輸入值；共同呼叫前 `RSP` 都是 wrapper 入口 `RSP - 0x20`。原本第 5–9 個參數仍留在原 caller stack 位置，其中第五個參數相對於此刻 `RSP` 位於 `+0x48`。

設 wrapper 入口 stack pointer 為 `S`。若錯把未知 dispatcher 替代為普通 `JMP RAX`，共同 `CALL` 壓入返回位址後，目標函式入口 stack pointer 會是 `S-0x28`。普通 x64 第五個參數的位置因而落在 `(S-0x28)+0x28=S`，讀到原 caller return marker；真正的第五個參數仍在 `S+0x28`。建立網路與建立端點的已保存 C API 簽章有 stack 參數，因此這個簡單跳轉模型不支援它們所需的傳參。

此反例限制我們的候選實作：在解析共同 dispatcher 前，不能用「RAX 已對上 export」作為直接替換轉接程式的理由。尚未讀到的原 dispatcher 可能處理 stack／返回路徑；本輪沒有推測其實作，也沒有證明完整呼叫 ABI。

新增報告：`output/native_dispatch_20261010/party_entry_call_boundary_20261016.json`，原六入口初版報告保留不覆寫。更新後測試 **13 項通過，退出碼 0**；XML 為 `party_entry_call_boundary_tests_20261016.xml`，完整 stdout/stderr 為同名前綴 `.log`。日誌保留 21 筆 Unicorn `mem_map` 的 Windows access-violation 診斷；測試程序正常結束，但不作為原生或遊戲穩定性證明。

另核對 r2–r5 舊 Party jump-chain 收據及兩份舊 external-slot 收據：r2 沒有成功的程式碼內容，r3 僅有短前綴／metadata，r4 與 r5 分別含 12、18 個完整保存程式碼範圍，兩份 slot 收據各含 9 個範圍；上述已核對範圍均未補出 `EXE+0x2EFAF2D`。另存的 `partywin_export_verification_20261011.json` 指紋與本次 PartyWin 相同，其選定 export 清單仍無 `0x19880`、`0x1BE80` 的名稱。這是有限保存資料的查核結果。

下一個具體動作是離線準備最小補充範圍與工具，針對共同 dispatcher 的固定目的地及兩個未命名 PartyWin RVA。新的實機或安裝映像讀取必須取得新授權；PID30776 的一次 v2 採樣授權已用完，不能再次使用。完整八人驗收與所有發布門檻仍未達成。

## 2026-10-16 共同 dispatcher 補充工具已離線完成，未授權執行

新增 `five_player_feasibility_20260927/tools/capture_party_dispatcher_supplement_20261016.py`，沿用 v2 的已驗證只讀後端和 64 KiB 計數器，另立固定的補充範圍。原 v2 工具及原始採樣收據沒有改動。本輪只寫工作區程式與文件、使用假讀取器測試並生成離線清單，沒有查詢遊戲程序或讀取安裝檔案。

補充清單：`output/native_dispatch_20261010/party_dispatcher_supplement_plan_20261016.json`。需要取得的新資料是共同目的地的固定 4 KiB 程式碼視窗，以及兩個 PartyWin RVA 的精確磁碟 export 名稱／ordinal。此範圍尚未獲得新的實機授權。

| 位置 | 單次長度 × 次數 | 小計 |
| --- | --- | --- |
| EXE、game.dll、PartyWin.dll 各自的 PE header | 每個 4096 × 2 | 24,576 bytes |
| game.dll + `0x108C18F` | 76 × 2 | 152 bytes |
| game.dll + `0x4EDAA4` | 36 × 2 | 72 bytes |
| EXE + `0x2C75FEC` 共同槽 | 8 × 2 | 16 bytes |
| EXE + `0x2C7A94D` 已知入口跳轉 | 5 × 2 | 10 bytes |
| EXE + `0x2EFAF2D` 固定 dispatcher 視窗 | 4096 × 2 | 8,192 bytes |
| **合計** | **16 筆請求** | **33,018 bytes** |

所有進程記憶體請求仍受 **65,536 bytes** 硬上限限制，包括校驗、復讀與失敗請求。EXE 基址來自新授權 PID 的當次載入資訊，不重用 PID30776 的絕對位址。共同槽必須指向當次 `EXE+0x2C7A94D`，該位置的五個 bytes 必須仍是 `E9 DB 05 28 00`，且解碼後必須恰為固定 `EXE+0x2EFAF2D`，才讀取已宣告的視窗。視窗必須完整落在驗證過的 EXE 內，並通過可執行 MEM_IMAGE 檢查；復讀不同立即停止。

另有三個完整磁碟檔案的指紋讀取：當次載入路徑對應的 `helldivers2.exe`、`game.dll`、`PartyWin.dll`，固定 SHA-256 與 v2 相同。只從同一份已驗證 PartyWin bytes 解析 export table，尋找 RVA `0x19880`、`0x1BE80` 的精確對應；保留 alias、ordinal-only 與 forwarder 資訊，沒有精確對應就記錄 `no_exact_export_match`，不猜最近函式名稱。這部分磁碟讀取，以及指定 PID 的路徑／模組／保護屬性查詢，不計入上述記憶體內容上限。

不讀六個入口 qword、原有六個候選槽、manager／heap 欄位，也不追蹤視窗內任何新跳轉或呼叫。4 KiB 不保證涵蓋完整 dispatcher；缺少的後續區段必須如實列出。版本不符、slot／入口變化、讀取失敗、程式碼復讀變化或預算不足均停止，不重試、不提權回退、不安裝插件、不呼叫 native 函式、不寫入遊戲。新輸出使用排他建立，已存在的檔案在打開進程前即拒絕覆寫。

離線驗證：`test_party_dispatcher_supplement.py` **18 passed**，XML 收據為 `output/native_dispatch_20261010/party_dispatcher_supplement_offline_tests_20261016.xml`。測試覆蓋完整 16 筆範圍與總量、預算上限、入口／復讀變化、完整模組邊界、停止收據與 handle 關閉、不跟隨視窗首條跳轉，以及精確 export 名稱／alias／ordinal／缺失結果。計畫模式已實際產生清單並回報 `process_accessed=false`。所有遊戲後端與磁碟檢查均以假資料或禁止入口替代，沒有實機執行。

取得新授權後才可執行以下步驟：

1. 使用者明確授權「按補充清單一次只讀採樣，保持 64 KiB 上限」，並提供當前 `helldivers2.exe` PID 及穩定單人飛船狀態。舊 PID 與上次授權不自動沿用。
2. 對該 PID 執行一次新工具，以全新工作區檔案保存收據；以下是未執行的模板。

```powershell
py -3.12 "E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\tools\capture_party_dispatcher_supplement_20261016.py" --pid <當前PID> --output "E:\File\Codes\0\26.10.1\HD2\output\native_dispatch_20261010\party_dispatcher_supplement_authorized_01.json"
```

3. 成功或停止後關閉 handle；後續只分析保存的程式碼與 export 結果，不自動重新擷取。

需要新授權的原因來自使用者對上一次「按 v2 清單一次只讀採樣」的明確限制：該次已完成，而新增的 `EXE+0x2EFAF2D` 視窗與 export 查詢不在那次清單內。新工具準備完成不代表採樣獲准，八人功能與發布門檻仍未完成。
