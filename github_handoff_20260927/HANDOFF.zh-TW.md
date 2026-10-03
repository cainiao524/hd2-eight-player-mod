# 接續狀態：2026-09-28 已恢復離線工作
## 2026-10-03 固定版本容量補丁實機載入

新增 `Native/CapacityPatch` 原生插件候選，固定 `Build 25480438` 與 35 個四人容量／枚舉／加入／狀態更新 site。插件先完成全 site fingerprint preflight，才以單一交易寫入 `8`；任一 site 不符就拒絕，卸載路徑按逆序恢復 bytes。

在 Steam 正常啟動的固定版本實機中，官方 loader 記錄 `loaded`、`applied` 且 `patched=35`；原始收據中的 `GameSessionCApi.num_peers`／`peer_count` 欄位已被 superseded，因為 HD2 的 wrapper/vtable 語義尚未閉合，舊探針不能把該偏移當作可靠 peer getter。實測後已停止遊戲並移除 DLL／marker。

這只閉合容量常數層，沒有證明 Party/PlayFab admission、第五至第八個 confirmed-peer、Player Clone、客戶端 entity replication、死亡增援、重連、撤離或 host migration。`installable=false`、`multiplayer_verified=false` 保持不變。研究與機器收據見 `CAPACITY_PATCH_CANDIDATE_20261003.zh-CN.md`、`live_capacity_patch_runtime_verification_20261003.json`。

## 2026-10-03 公開倉庫研究與官方 C API 邊界捕獲

已固定閱讀三個新增公開倉庫：`MrChengl11/hd2-lua-mod-skill`（`d1811983ab4fec230ede24bdd3d274f77b0b82fd`）、`junze0910/junze-hd2-lua-mod`（`95b2d26ea10ea43281c93123a95d326a289da2ae`）及 `starmatch666-droid/hd2-mod-update-skill`（`2eae30596a0886b4674567f22f549ef03e9b80e4`）。研究結果已寫入 `PUBLIC_CODE_RESEARCH_20261003_NEW_REPOS.*`：可採用離線／唯讀探測、UI 第五槽位寫入風險與 build/hash/table fail-closed 門檻，但三者都沒有 Party → Session → Player Clone 的八人能力證據。

同一固定 build `25480438` 保存了 `Network`／`GameSession` C API table 的 bounded prefix 和候選 engine-session vtable 的靜態前綴。捕獲只讀、重讀相等、沒有呼叫函式、寫記憶體、hook 或注入；wrapper table 與 underlying vtable 分開記錄，不能解讀成 peer admission、player creation 或可安裝 Mod。

最新研究提交為 `799e5b6`，狀態收據提交為 `c4fcaba`。`installable=false`、`multiplayer_verified=false`、真實第五至第八帳號測試未完成。


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

这只提供固定版本的 layout 观察工具，不是玩家 admission 或 Player Clone 建立。当前第五至第八个账号、客户端复制、死亡/增援、重连、结算和 host migration 仍未验证；`installable=false`、`multiplayer_verified=false` 保持不变。最新研究提交为 `2136c72`，状态收据提交待本节更新后产生。
