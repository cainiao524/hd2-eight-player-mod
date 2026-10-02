# 《Helldivers 2》五人加入／八人同場 Mod：可行性研究

## `0.14.0-offline`：6054F0 狀態更新接入共同八格儲存

[狀態更新候選](../eight_player_candidate_20260927/NATIVE_ROSTER_ARRIVAL.zh-TW.md)已完成離線交付收尾：完整 1111-byte 原 body 產生 1917-byte 候選，19 個 pointer／primary／aux／property 位點改接共同 B；入口檢 binding、counts、map、ordinal、target 與 caller-state。原四列 palette 及 network index≥4 的白色 fallback、三處 current-D 通知、frame／cookie／calls 保留。`arrival` 只是檔名，此函式沒有 append 或 count 遞增的證據。

[5 組／42 次指令驗證](../eight_player_candidate_20260927/verification/native_roster_arrival_tests.json)包含原版完整返回4、候選完整返回21、入口拒絕17；巢狀 FD9AF0 的25次另列。19處靜態核對、17處有效域動態檢查，6056C8／6056D6只有靜態覆蓋。[Source審查](../eight_player_candidate_20260927/verification/native_roster_arrival_review.zh-TW.md)及[接續 oracle 審查](../eight_player_candidate_20260927/verification/native_roster_arrival_test_review.zh-TW.md)已保存；接續重跑42筆紀錄與凍結報告相同。

共同 bundle 為 **16個 roster 函式＋原 player_count 計畫、62個已知區域**，內嵌 v0.13 產物相同。累計 **149組／4,314次套件執行或觀察**，包含原版、拒絕、前綴觀察與預期反例，不能稱為候選成功次數；重跑與巢狀helper不重複計數。15個既有來源與14份舊報告未改，舊套件未重跑。

Sidecar配置／發布／清理、其他reader、caller／callback同步、真實資源、reject handler、hook／Windows unwind仍缺；目前不可安裝，五至八帳號同場任務未驗證。後續P3的[1277920有限調查](roster_mask_reader_findings.zh-TW.md)已固定兩個roster讀取與mask前綴：primary+24h和property+Ch都需改接B；24次原前綴觀察未見mask分支造成後續狀態差異，不列入交付套件數。下一步是明確入口guard／普通missing政策並實作完整reader候選。

日期：2026-09-27。範圍：**同一場任務中出現第五位真實玩家**，作為八人同場的第一個門檻。本報告使用公開的一手資料、本機既有檔案，以及使用者分別同意並手動啟動遊戲後的三次限定唯讀擷取。擷取完成於香港時間 12:02:53、12:15:19 與 12:49:36；沒有修改遊戲檔案或程序，也沒有執行第五人連線測試。

目前完整目標為**完成並驗證 HD2 八人同場 Mod**。第五人是中途驗證步驟；研究工具、可載入 addon 或靜態分析通過都不算完成八人 Mod。此目標尚未完成。

依更新目標整理了[最小必要阻礙與實作工作清單](IMPLEMENTATION_WORKLIST.zh-TW.md)，保留平台加入與第五人角色建立為優先門檻。另已完成[節點配置前檢查候選Lua元件](../eight_player_candidate_20260927/README.zh-TW.md)及獨立LuaJIT離線測試，將轉換峰值與partial／同ID問題轉為可整合的診斷程式；一致snapshot、執行保護、原生executor與多人結果仍未具備，沒有安裝或接入遊戲。

候選現另有[二進位資料驗證器](../eight_player_candidate_20260927/SNAPSHOT_CONTRACT.zh-TW.md)，核對提供的 descriptor、全池占用、S indices、模板／context 與已知區域，再接到配置前檢查。20 組新增測試及原 11 組測試通過；獨立審查提出的 free payload 漏檢已重現並修正，保留初始化／清理兩種已知格式。這些是合成 bytes 的候選程式驗證，不是 live heap、同步時點或八人實測證據。

`0.3.0-offline` 加入[已知 owner 地址規劃與覆蓋檢查](../eight_player_candidate_20260927/OWNER_LAYOUT.zh-TW.md)：四份玩家 records 對應 305 個已知 S，八份獨立儲存對應 325 個，其他 285 個地址與順序保留。它拒絕漏列物件、搬移後舊副本及整筆玩家 record 的已知碰撞，然後接到既有 bytes 驗證器；這仍未配置或搬移原生記憶體。

另完成[20 筆雙 S](indexed_float_pool_double_records_findings.zh-TW.md)、[七個單例](indexed_float_pool_singletons_findings.zh-TW.md)及 [ID0 條件契約](indexed_float_template_zero_findings.zh-TW.md)的離線重播與審查。雙 S 陣列的全部 40 個實體物件必須保留，即使 active count 為零；主模板 1F 為一格，第二 S 的完整模板／保留資源來源仍缺。七個單例固定模板子集合條件式至多 12 格；ID0 只在實際資料驗證 count0 及所有權一致後列入單一 S 轉換計畫。上述均不能證明全池上界、全域回收、原生恢復成功或八人功能。

`0.4.0-offline` 加入 [roster property receiver 原生候選](../eight_player_candidate_20260927/NATIVE_RECEIVER.zh-TW.md)：保留 `60C890` 的完整查表／copy／cursor 流程，只重定位外部 RIP 讀取及 `60C932` 的六 byte 切點，將符合綁定且 ordinal 為 0..7 的寫入導向八份獨立儲存；不符時轉到整合者必須提供的拒絕入口。這是離線產生的 375-byte x64 候選，尚無可啟用的 hook／unwind／reject handler；其他 roster producer 與讀者仍須共同改接。

此候選已通過[獨立靜態審查與 x64 模擬執行](../eight_player_candidate_20260927/verification/native_roster_receiver_review.zh-TW.md)：11 組測試、52 次指令執行，涵蓋八個 ordinal、不同 network index、cursor、碰撞查找、拒絕分支、暫存器與重定位邊界。合成記憶體中的通過結果不能替代 Windows unwind、真實 caller／引擎同步或多人驗收；原版第 5–8 格的比較使用刻意加大的合成區域，沒有證明原遊戲四格儲存可直接容納八份。

`0.5.0-offline` 再加入 [producer 與 receiver 共同建置候選](../eight_player_candidate_20260927/NATIVE_PROPERTY_PAIR.zh-TW.md)。真正 producer 入口 `60C640` 的完整 578-byte 函式產生 662-byte 候選，於 allocator 前檢查 ordinal／global roster，保留八個 descriptor 與初始資料，將 property 寫向共同八格儲存。10 組測試／54 次 x64 執行通過，包括保存的 index helper 及 producer→receiver 的同 S／跨 S 資料格式橋；allocator 僅採成功契約，沒有跑真實配置、serializer 或網路。另 4 組共同建置測試核同一綁定及跨程式區域交疊。當時依[有限存取清單](roster_property_consumers_native_findings.zh-TW.md)選定的 `60C410` 搬移已納入下述 0.6；其他讀寫者與生命週期仍缺，仍不可安裝。

[第二S來源的有限收束](indexed_float_double_secondary_findings.zh-TW.md)沒有找到可接合同D的配置入口；[P5整合邊界](native_integration_boundary.zh-TW.md)亦確認正常call順序不能證明引擎同步，update後檢查只能後驗。兩條支線保留明確缺口，待具體新來源才重開；當前離線實作重心轉至P3名冊原生存取。

`0.6.0-offline` 已完成 [四組完整名冊搬移與三函式共同建置](../eight_player_candidate_20260927/NATIVE_ROSTER_BUNDLE.zh-TW.md)：`60C410` 的 pointer、70h、38h、20h 記錄共用 `680h` 八格儲存，保留原 S 的 map。新增 11 組／103 次 x64 模擬執行通過 64 種搬移、原四格對照、拒絕與 producer→move→receiver 串接；接收端確實依更新後 map 寫入新 ordinal。独立靜態審查未發現此局部改接缺陷。這使 P3 的記錄搬移更接近實作，但插入、壓實、分類、移除、其他讀者與執行整合仍缺。

[初始化前提核對](roster_move_native_prerequisites.zh-TW.md)另確認原 constructor 不會初始化全部四組記錄，加入分支有保留欄位及非零預設值。因此新槽不能直接以全零視為有效；下一步需保留各插入路徑的原生初始化次序。沒有新增遊戲程序操作或多人驗收。

`0.7.0-offline` 新增[四插入與七函式共同建置](../eight_player_candidate_20260927/NATIVE_ROSTER_INSERT.zh-TW.md)。四個 body 的 56 個直接 array stores 改接相同八格儲存，入口以 T<8 阻止回繞，核對分段計數，dense 插入額外拒絕未證安全的 pending-tail 狀態。9 組／515 次 x64 模擬執行通過原四格對照、全部支援的分段／旗標組合、同一名冊八筆追加及第九筆拒絕、插入→producer→receiver。實際執行保存的 map helper／mover；allocator 與 incoming bytes 仍為合成契約。独立 source／oracle 審查已完成，報告的跨階段累計數已修正。沒有八帳號或遊戲執行。

插入候選要求有效map、新key、同步，以及dense D==T；後者尚未證明所有caller都滿足。後續[原四格整理反例](roster_compact_counterexample.zh-TW.md)已否定 `60CC70` 可單憑 `P≤D≤T` 直接擴容的假設：原指令先 P→D，再將已覆寫的 D 複製回 P。原四格 35 種合成分段有 10 種失去原實體及正確 map；原 dense／append／compact 的合成序列亦可重現。這沒有證明遊戲實際 dispatch 可達該狀態。尚未產生 compactor；先釐清已註冊 append 的派送及 pending 所有權，再決定整理實作。其後仍需分類、移除、讀者與完整生命週期。該輪未新增 compactor，八人目標未完成。

`0.9.0-offline` 新增[八格分類切換與十一函式共同建置](../eight_player_candidate_20260927/NATIVE_ROSTER_CLASSIFY.zh-TW.md)。完整 `60CF50`／`60D300` 的 88 個 array operands 改接共同 B，保留原移入清零／移出完整交換差異、兩筆 map 與暫存 scope 次序；前置 guard 拒絕缺失 ID、無效方向及不符過渡旗標。獨立靜態審查核全部 429 條原指令。合成指令測試涵蓋八格合法分段、原四格配對及換位後接收；暫存 helper 使用明示成功契約，並非真實配置器執行。外層旗標／通知已先發生時不能靠局部拒絕回復，這是整合缺口。

`0.10.0-offline` 新增[完整 ID→network-index getter](../eight_player_candidate_20260927/NATIVE_ROSTER_GETTER.zh-TW.md)，原 165-byte／43 指令函式產生 354-byte 候選並加入十二函式 bundle。保留完整 DWORD、普通 missing 與 pending 讀取；成功查找後拒絕越界／非 active ordinal、空 bucket stale value 假命中。7 組／84 次執行含 73 候選／串接、10 原基準、1 預期原假命中；分類與原生 map-delete／候選搬移後，ID 67 在不同 ordinal 讀回相同高位值，已刪 ID 返回 missing。來源及 oracle 獨立審查完成；其他 readers、caller／sidecar 生命週期及八人實測仍缺。

[移除前處理續查](roster_departure_native_findings.zh-TW.md)固定 `605950` 的六個直接陣列讀取及額外 `606820` network reader，並確認它先清理／通知，真正名冊移除在較後派發。三個原四格合成案例重現：pending 成員離開時兩個通知傳 D−1，而隨後原 `540A40` 保留 D；D=0 時兩個參數均下溢至 FFFFFFFF。這是明示外部通知不干擾前提下的原指令結果，真實 caller 是否可達 pending 未證明。另有[必要 callee 前提](roster_departure_native_prerequisites.zh-TW.md)：`94C9C0` 將 count 限制在 1..4，發 `num_players` 並傳給 `94BE10`；`60C2A0` 僅有四種命名資源分支，其餘值仍走數值通知。這些限制需要納入八人通知／資源方案，不能只改六個讀取便稱完成 departure。在該移除前調查完成的 0.10.0 階段，尚未新增 departure emitter，也未加入候選通過數。

`0.11.0-offline` 新增[玩家數 patchplan](../eight_player_candidate_20260927/NATIVE_PLAYER_COUNT.zh-TW.md)：`94CA30` 的 5-byte 原位立即數將上限 4 改 8；`94C07B` 的 6-byte 切點導向 51-byte 近端 trampoline，僅在來源 record **max=4 且 min≤4** 時把上界視為 8，保留其他範圍、原始 0→1 clamp、override 與獨立 tech-level 索引。此政策令符合 `1≤min≤max≤4` 的來源 profile 在候選 count 5..8 下沿用原 count4 選集；它是新增的候選規則，並未證明目前遊戲資產的實際 min/max 值。[完整 `94BE10` 原指令與切點](roster_player_count_native_findings.zh-TW.md)及[必要 count 契約](roster_player_count_native_prerequisites.zh-TW.md)已從固定 capture 核對；[原生 source](../eight_player_candidate_20260927/Native/player_count.py)只產生離線 bytes／patch 計畫，不安裝到遊戲。

[7 組 player-count 測試](../eight_player_candidate_20260927/verification/native_player_count_tests.json)含 188 次 x64 模擬觀測：**162 次完整 `94BE10` filter**（65 原版、97 候選）與 **26 次只到 `94CA3A` 的 `94C9C0` prefix** 分開計數。它核 1..4 原行為、有效四人 profile 下候選 5..8 對原4的 whole-page／D8輸出等價、`min5/max4` 空範圍、override、tech 1/3/10 及真實 tag predicate；四個其他 callee 以明示成功契約代替。[獨立 oracle 審查](../eight_player_candidate_20260927/verification/native_player_count_test_review.zh-TW.md)未見局部阻塞缺陷。截至 `0.11.0-offline` 累計 **129 組／4,142 次套件觀測**，包括原版基準、26 次 prefix、既有預期原反例及候選執行；不能將 4,142 次稱為候選成功或完整 context 執行。

`0.12.0-offline` 再加入[八格名冊離隊前處理候選](../eight_player_candidate_20260927/NATIVE_ROSTER_DEPARTURE.zh-TW.md)：固定完整 `605950` 的 1,503 bytes／346 條原指令，六處 pointer／primary／property 讀取改接共同 B，`6059EE` 這一處改呼既有八格 getter；原三個 primary helper、關聯物件支線、manager 迴圈、通知與間接尾跳保持。新增入口 guard 在執行原主體及其回呼前查驗 S/B、entity、map／ordinal 與分段；兩個通知改用明示候選政策 `D−(ordinal<D)`，因此在穩定狀態下 pending 離隊保留 D，包括 D=0 不再下溢。尾部 `player_count` 仍讀真正移除前當時的 D。[候選契約](roster_departure_candidate_contract.zh-TW.md)明列回呼至後續 `540A40` 的序列化與生命週期前提，入口 guard 本身無法提供該保證。共同離線產物含 **十三個 roster 函式與前版 player-count patch 計畫**，沒有執行安裝。

[7 組 departure 測試](../eight_player_candidate_20260927/verification/native_roster_departure_tests.json)通過 **43 次頂層 x64 執行**：7 原四格基準、16 候選完整 departure、17 候選 preflight 拒絕、1 次候選 remove 與 2 次 getter 串接。保存機器碼的三個 primary helper、關聯 getter、map-delete 實際執行；外部關聯資源、manager queue、兩個計數接收者及尾部通知以明示 ABI／順序替身測試。[獨立 oracle 審查](../eight_player_candidate_20260927/verification/native_roster_departure_test_review.zh-TW.md)未見此有限測試的阻塞缺陷；不能把替身成功當成真資源相容。截至v0.12累計 **136 組／4,185 次套件觀測**，仍包含前述 26 次 prefix、原版基準、拒絕及預期原反例，並非 4,185 次候選成功或完整遊戲執行。

真實 R8/R9 資產 record 範圍、`94C9C0` 十五個完整 callsite 端到端路徑、`605950` 回呼期間及後續移除的 state 序列化、原生 sidecar 配置與其他 alias、hook／拒絕 handler／Windows unwind、資源和八帳號同任務驗收都未完成。原 pending D=0 的下溢已由候選的兩個參數消除，`94C9C0` 對輸入 0 仍夾至 1，`60C2A0` 對 5–8 沒有已證命名資源。B54E00與必要606520改接已納入下述v0.13；P1 平台加入與 P2 角色建立等外部缺口維持。

## `0.13.0` Registry 更新與關聯 ID reader 共用 B

[固定來源](roster_registry_update_native_findings.zh-TW.md)與[必要前提](roster_registry_update_native_prerequisites.zh-TW.md)收束完整 `B54E00`、其必要 `606520`，另固定 test-only `FD9BA0`。[候選](../eight_player_candidate_20260927/NATIVE_ROSTER_REGISTRY_UPDATE.zh-TW.md)將 root 六處與 helper 兩處 pointer／property／aux 基址改接共同八格 B；保留其他 tags、D 遍歷上界、entity flag 規則與兩個 helper 各自的 7FFF 語義。tag69、tag73 使用 roster 前才驗 binding/counts；tag69 匹配後另驗 map 容量、key 及有效且與 property ordinal 一致的 map 結果。共同產物為 **十五個 roster 函式＋不變 player_count 計畫**，59 個已知區域核對通過，嵌入的 v0.12 產物一致。

[8 組／87 次頂層測試](../eight_player_candidate_20260927/verification/native_roster_registry_update_tests.json)分為 **12 次原版完整基準**（root8、helper4）、**49 次候選完整返回**（root32、helper17）及 **26 次候選拒絕**（root20、helper6）。tag69 實際執行保存的 FD9BA0；tag73 實際進入原版或新606520。其他tags的資源calls由明示 ABI／順序／副作用替身提供。全部八格、dense-only／普通miss、aux狀態保留、bit旗標、其他tag、混合registry、拒絕恢復、地址與rel32邊界均有有界案例；沒有新增remove/getter串接執行。巢狀helper不重複加入頂層數。

v0.13當時累計 **144 組／4,272 次套件觀測**；總量保留舊版26次context prefix、原版基準、拒絕與預期原反例，並非4,272次候選成功。[Source審查](../eight_player_candidate_20260927/verification/native_roster_registry_update_review.zh-TW.md)及[oracle審查](../eight_player_candidate_20260927/verification/native_roster_registry_update_test_review.zh-TW.md)各自記錄範圍。原14個候選來源及13份報告保持原指紋，未重跑舊套件；新CLI建置逐byte等同保存的完整bundle。

這不提供引擎同步、有效context map／backing／resource、hook／unwind或nested reject handler。較早registry entries可在較晚拒絕前產生副作用；零容量／full-miss context map的原null缺口亦保留，不能視為任意輸入皆安全。該輪6054F0切點已由上述v0.14接入；後續reader見最新工作清單。平台加入、角色建立與五至八帳號任務全流程仍未驗證。

## 結論

`0.8.0-offline` 已完成[兩種原生移除與九函式共同建置](../eight_player_candidate_20260927/NATIVE_ROSTER_REMOVE.zh-TW.md)。原 helper 在 missing ID 時回 0，原 dense 移除在 D<T 時又會漏保留 pending 尾端；候選先查存在性／ordinal／目標 prefix flag，再保留原 prefix／dense 搬移並補上 tracked-tail→new-pending-start。這是新增候選語義，支援全部有序八格分段；沒有用 D==T 限制代替混合分段。9 組測試含 2,293 次執行（候選 2,141、原四格基準 150、預期原反例 2），通過所有分段／目標、原 ABI、拒絕與八筆追加→移除→再追加→接收串接。獨立 source／oracle 審查完成；外部 ownership／caller／同步仍未證，尚不可安裝。

[追加表派送的有限查核](roster_append_dispatch_findings.zh-TW.md)已確認整理更新鏈 `FDC780→576CF0→60CC70`，但尚未找到第一張 `F0B6F0` 表的實際 reader。已證建立路徑只讀第二張 `F0C110` 表，無法據此閉合 pending 所有權。此支線取得具體計算地址來源或新保存資料前不重複泛查；移除、分類、getter 和離隊前處理已有各自離線候選。`94BE10` 玩家數與 `605950/606820` 改接共同 B 的局部資料流已固定；跨回呼的 count/state 穩定性仍是外部整合契約。v0.13已將B54E00及必要606520完整改接；6054F0已納入v0.14，下一有限P3切點是1277920，pending 生命週期及其餘 alias 仍需具體證據。

**已核對房主加入、客戶端 peer 記錄、原生玩家 roster 的四人限制，以及擴至第五筆時的相鄰欄位衝突。** 另有實際 gameplay／復活更新只建立四個候選。兩次限定唯讀擷取已定位並分析兩條平台介面路徑；「設定加四」的結構與 PlayFab Party 網路使用者／裝置上限配置高度吻合，但具名函式綁定與服務回應仍未取得。因此單純更改大廳顯示、好友房間或一個 `MaxPlayers` 數值，不能構成五人可玩的證據。第五人能否通過平台房間／遊戲服務、在所有客戶端生成並同步、完成任務與結算，目前都是**未驗證**。截至本輪，沒有可交付的五人或八人 Mod。

這是「已發現本機端障礙、尚未證明全鏈路可行」的結論，不是八人 Mod 永遠不可能的證明。

第三次限定擷取另外定位了名單 handle 介面：`EXE+0x30ff50` 是九條指令的轉接入口，將資源 hash 改為按地址傳給 `EXE+0x1ae380`，再讀取返回指標指向的 32-bit 值。此入口沒有四／八容量比較；其下游尚未保存，不能推論角色配置沒有上限。詳見[第三次擷取分析](spawn_interface_findings.zh-TW.md)。

[既有資料覆蓋核對](spawn_callee_availability.zh-TW.md)已確認七個 EXE 保存窗口都不含該下游。雖然磁碟上有其 RVA 的 raw backing，同區域已知入口的磁碟 bytes 與載入後 bytes 不同，不能直接套用磁碟內容來補上函式實作。

後續離線研究已補上**元件 239 → 已登錄的四槽 roster 插入 → `index` 屬性**的程式關係，並在 FileDiver 參考資產清單找到 player 包含 239。參考資產與目前載入內容尚未證明相同；這使原生修改位置更明確，仍不構成五／八人可玩的驗證。

再往下核對九個參考 player 元件，**七個第一階段 callback 都有四筆護欄**，其中五個是新確認的元件；數組擴容會與實際使用的相鄰記錄重疊。本地加入流程也已用完整正常控制流程證明：network index 4–7 會略過該流程唯一已確認的 player 資源建立呼叫，之後仍可繼續同步及 ready 檢查。因此「已入隊／繼續同步」不能作為第五名玩家生成成功的判準。詳見[元件容量](player_component_capacity_findings.zh-TW.md)與[本地建立護欄](local_player_creation_gate_findings.zh-TW.md)。

新增五個元件的生命週期續查已補出更多平行陣列、逐 ordinal bytes、外層成員邊界及 registry 指標副本；33 原先不明的 `+0x90` 與 250 的 `+0x160` 都有實際用途。現已整理[八槽儲存設計約束](PLAYER_COMPONENT_RELOCATION_PLAN.zh-TW.md)，優先核對保留原元件物件地址、另配置陣列的方案。完整讀寫集合仍未收束，沒有產生或套用原生補丁。

本次離線續查又補上三個缺口：**roster 的 `index` 接收會原樣保留 32 bits；選定 property 格式逐 entity 消耗 280 bytes；原先容量未知的雙 float writer 確認只初始化四筆，索引 4／7 的寫入會覆蓋相鄰資料。** 元件 43 也另有不經共用 helper 的內嵌更新路徑，已加入改接範圍。詳見下方接收、分派及索引儲存續查；這些是原生實作約束，尚無執行中的八人原型。

最新容量研究已將九個參考 player 元件分清：**七個固定四筆，元件 3／260 則分別初始化 512／64 筆並能動態增長**，後兩者在已核對的容量路徑可保留既有機制。八項共用 map 的離線模型也完成滿載、刪除、重插與指令對照，支持在有效 key 與容量等前提下保留八 buckets。這些結果縮小了必要修改範圍，沒有替代原生補丁與多人測試。

雙 float 物件的有限 consumer 清單亦已補上：除了四筆 records，還有兩張四格 metadata 表、四格 stack 索引表，以及三張只初始化三項的 rank→ID 表。**若非本機 network index 4 走到該 stack writer，會覆蓋稍後仍使用的 ID。** 更新流程還有「每次兩筆、迭代兩次」的四筆展開，不能只搜尋 `cmp 4`。八人設計需共同處理這些空間與存取；找不到 selected local/current index 時，rank 甚至可能有八項。

後續又接上三個實作邊界：外部 q 是按host peer查得的既有confirmed-peer network index；記錄內子物件共用256格pool，新增實例須各自初始化且處理池滿的部分配置；三組rank ID則連到Wwise音效介面。已從本機同build的boot資產唯讀取出映射，確認六個事件hash存在，但兩個浮點參數hash在該保存表中缺失。這些結論限定保存程式及所選資產，仍未形成原生八人補丁。

最新[模板節點預算](indexed_float_template_budget_findings.zh-TW.md)確認四段建立流程分別加入5／1／3／1格；五個玩家子物件合計每筆11格，新增四筆44格，八筆88格。此預算以執行期模板等同所分析結果為條件，尚未測量其他共用池用途／峰值；256格是否足夠仍待證明。

[初始零值來源續查](indexed_float_pool_initial_zero_findings.zh-TW.md)又接上外層配置的`7AF7628`-byte zero-fill：經同一owner／manager鏈，pool descriptor、used count、cursor及occupancy均在最初清零範圍內。這解釋初始來源，沒有證明後續重入時仍為零或可安全reset active pool。同一owner setup也明確呼叫模板建立函式`1258050`，但未觀察live模板內容。

[直接生命週期清單](indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)已確認`142B990`與`142C9B0`的305個S建立／清理位址及順序相同，其中20個屬玩家記錄。八筆需共同涵蓋325個S；保留原基底僅增次數有27組S範圍衝突，Python獨立儲存推演可使這兩條清單一致且無重疊。這仍是有限位址投影，沒有執行引擎釋放或完成全部consumer改接。

[其他成員模板續查](indexed_float_pool_optional_members_findings.zh-TW.md)又確認`20/21/2F/22`四個主模板各一格，指定四組callers的配置需求在物理上限前提下最多72格。其共用helper對可選S的false旗標路徑沒有直接cleanup，因此整池預算仍需納入先前保留的配置，不能只依目前啟用項目估計。

[Counter與快取續查](indexed_float_pool_counter_bounds_findings.zh-TW.md)已把四組容量接到四個清零store與五條guarded append：有效初值及無其他writer干擾時，維持1／64／5／1上限。另核清零後段266處直接D寫入，不碰305個已盤點S或pool，故count歸零不能當作已回收節點。`D+8D709`控制builder快取；其餘旗標writer、所有aliases與完整回收生命週期仍待閉合。這補強72格子集合需求，仍未證明256格整池足夠或八人聯機成功。

[32筆三S模板續查](indexed_float_pool_triple_members_findings.zh-TW.md)又接上逐筆模板表及12個模板的節點數。對已列模板域，單筆最後需求3至5格；保存順序的局部轉換模型卻可先需要6格、最後回到5格。只留5格的模型會partial配置，下一次同ID也不補齊。這要求八人方案計入轉換餘量或失敗處理；模型有明列的caller／模板／不干擾前提，沒有證明實際遊戲必經這些狀態或整池目前必然耗盡。

## 固定來源與核對

| 項目 | 本輪核對結果 |
|---|---|
| 官方現行人數 | [Sony 2026-08-12 新聞稿](https://sonyinteractive.com/en/press-releases/2026/helldivers-2-joins-the-playstation-plus-game-catalog/)與[Arrowhead FAQ](https://arrowhead.zendesk.com/hc/en-us/articles/12571604061212-Helldivers-2-FAQ)均寫每隊最多四人。 |
| 網路與防作弊 | [Arrowhead 技術總監聲明](https://steamcommunity.com/app/553850/discussions/2/4206994023681287288/)說明任務採 P2P，銀河戰爭另有雲端服務，並使用 GameGuard。P2P 不代表房間建立、入隊、進度與所有其他步驟都只由房主控制。 |
| 本機遊戲 | Steam app `553850`、build `25480438`；`helldivers2.exe` 版本 `1.8.46015.0`，SHA-256 `f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06`；`data/game/game.dll` SHA-256 `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e`。與既有離線捕捉記錄吻合。沒有更動安裝檔。 |
| 既有捕捉 | 原研究 repo 的 `build/existing-code-evidence-25480438/`：`capture-report.json` SHA-256 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`；`captured-data.bin` SHA-256 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。由[唯讀讀取器](../research_handoff_20260927/indirect/inspect_capture.py)在載入時核對。捕捉只包含選定範圍，不含完整可寫全域資料或 heap；跨多次讀取，並非原子快照，`runtime_verified=false`。 |
| 工作區模組工具 | [FileDiver](../FileDiver/README.md)是遊戲資產提取器；[Bingus Shared Loader v18](../loader_v18_compat_20260927/external/v18/source/README.md)啟動 Lua 模組，其本體不更改玩法或執行程序記憶體寫入。現有 P-11／投射物模組不含大廳或網路容量實作。 |

## 指定參考專案的適用範圍

使用者提供的兩個 GitHub 專案已按固定提交查閱。它們降低製作和部署 Lua 研究 addon 的門檻，但沒有提供已運作的五人加入程式碼：

| 專案 | 已提供的能力 | 對五人加入仍缺少的部分 |
|---|---|---|
| [MrChengl11/hd2-lua-mod-skill](https://github.com/MrChengl11/hd2-lua-mod-skill/blob/d1811983ab4fec230ede24bdd3d274f77b0b82fd/README.md)，提交 `d1811983` | 作者明示它是**教學技能，不是 Mod**；[SKILL.md](https://github.com/MrChengl11/hd2-lua-mod-skill/blob/d1811983ab4fec230ede24bdd3d274f77b0b82fd/skills/hd2-lua-mod/SKILL.md)提供離線資料表、LuaJIT／FFI、唯讀偵察、資料修改與測試流程。案例主要是武器、投射物及戰備資料。 | 沒有經驗證的大廳／入隊／`HostSynchronizer` 容量 API 或第五人同場案例。作者亦將其效果界定為客戶端本地修改，可能不會同步給其他玩家。其資料表布局不能當成 native peer 槽位布局。文件中的 loader 版本例子較舊，不能照抄其版本常數。 |
| [CowboyBingus/BingusSharedLoader v18](https://github.com/CowboyBingus/BingusSharedLoader/releases/tag/v18)，提交 `3d7e3a12` | [Authoring](https://github.com/CowboyBingus/BingusSharedLoader/blob/3d7e3a120828178573ef1ee0a5c7eeae4a951865/docs/AUTHORING.md)與[程式碼](https://github.com/CowboyBingus/BingusSharedLoader/blob/3d7e3a120828178573ef1ee0a5c7eeae4a951865/src/shared_loader.lua)提供 Lua addon 發現、載入、記錄與共享 LuaJIT 預算；支援本輪遊戲 build。此版 coordinator 的內部版本為 `17`、API 為 `1`。 | [技術說明](https://github.com/CowboyBingus/BingusSharedLoader/blob/3d7e3a120828178573ef1ee0a5c7eeae4a951865/docs/TECHNICAL.md)明言 loader 本身不寫入程序記憶體，亦沒有房間或 peer 容量實作。`loaded` 日誌只證明 addon 已被載入，不能證明第五人加入或同步。 |

可行的用途是未來封裝**單獨設計且有版本檢查的研究 addon**。本機既有[唯讀 FFI 適配器](../pcf_four_scope_test2_v18_20260927/Source/runtime/image_windows.lua)可讀取模組映像，適合核對版本指紋；目前仍未找到已驗證的 Lua 加入事件回呼或執行期 `HostSynchronizer` 物件指標。因此即使 addon 成功載入，也無法據此觀察第五人的實際入隊結果。是否能藉 Lua／FFI 安全地處理 native 四人檢查、四槽資料與其他線上層次，這兩個專案都沒有證明。本輪只採用技能的離線優先方法，沒有安裝外部技能、載入 addon 或修改遊戲。

## 已核對的本機端四人判斷

在既有捕捉中，RVA `0x108c18f–0x108c1db` 的 76 bytes SHA-256 為 `e56eba5ea8a480553db61f70a65f1e036bd9ef81946ad7c8208832e1c700858a`。反組譯顯示：

```text
0x108c18f–0x108c1b2  計算一個基礎佔用者與三個非零槽位的佔用量
0x108c1b5               mov ecx, 4
0x108c1ba               sub ecx, eax
0x108c1bc               cmp ecx, r13d
0x108c1bf               jae 0x108c1db
0x108c1c5               mov r8d, 4
0x108c1d1               call 0xbe3cf0
0x108c1d6               jmp 0x108c59e
```

`r13d` 在 `0x108befd` 從加入請求讀取 32 位元成員數；`r14d` 在較早的 `0x108bd0b` 清零，故此段將 **4 減去已佔用量**，與請求成員數比較。不足時呼叫 `0xbe3cf0`，然後離開該處理流程。`0xbe3cf0` 的確切函式名稱與回應格式尚未確認；不能把它寫成已驗證的「伺服器拒絕」函式。處理流程還在 `0x108c2cb`、`0x108c393`、`0x108c3e2`、`0x108c4a1` 以 4 作迴圈界限。另一段 `0x108c420` 的 8 次迴圈用途不同，不是八人房容量證據。

獨立重播核對同一函式的 `HostSynchronizer`、加入請求與保留 peer 日誌，及從 `+0x20` 開始、間距 `0x38` 的四個 peer 欄位掃描，確認這是**房主的加入請求流程**。基數 1 所代表的首個佔用欄位仍是靜態推斷，未經執行期驗證；`0x108c1db` 只表示通過此項容量檢查，後面還有檢查。已有證據足以排除「只改一個顯示上限就能支持第五人」的簡單假設，**不足以推斷應修改哪些指令或修改後會成功**。

## 續查：加入判斷之後的四槽結構

同一固定捕捉的[加入流程重播記錄](join_handler_followup.json)列出 unwind 片段邊界、關鍵指令範圍的 SHA-256 與分支。它顯示容量比較後還有多層檢查與資料結構界限：

| 流程 | 靜態可見行為 | 對第五人的意義 |
|---|---|---|
| 容量檢查後 | 全域狀態檢查與逐位請求成員檢查可提前離開；可見數值 `9`、`6`、`5` 都經 `0xbe3cf0` 轉入結構化呼叫。 | 通過 `4 - 已佔用量` 的比較不等於接受入隊；數值的業務意義與網路回應未核實。 |
| 房主 peer 記錄 | `host+0x20+0x38*i` 的 `i=0..3` 四筆記錄；另有 `host+0x100..+0x103` 四個索引位元組。重複成員清理函式也掃四筆。 | 加入成員的記錄、索引與清理路徑都以四格為界。 |
| 待處理記錄 | `host+0x808+0x40*i` 的 `i=0..3` 四筆；找到空格時複製請求，四格皆滿時該段直接退出。 | 還存在一個獨立的四格上限；靜態資料不能確定全滿分支在正常流程是否可達，也未觀察到此處立即送出成功結果。 |
| 8 次迴圈 | `0x108c420` 掃另一個全域表的八筆鍵值，找到匹配項就清除該項及相連的 32 位元組區塊。 | 此表與房主 peer／待處理記錄分離；無法由此推論支援八人。 |

對 `0x108bc70` 的有邊界直接呼叫掃描只找到 `0xb93406` 與 `0xba8e13` 兩處；兩者都在先檢查註冊記錄的種類標籤 `0xEC` 後呼叫。後者所在函式 `0xba8cc0` 也出現在 captured readonly 的連續函式指標表。它先讀取輸入計數，按計數把成員資料複製到固定堆疊佈局；此處未找到顯式四人拒絕比較。詳見[上游路徑補充](UPSTREAM_JOIN.zh-TW.md)與[呼叫位置掃描](host_join_xrefs.json)。後續初始化追查把此標籤連到已註冊房主物件，故更正先前的「事件種類」用語；它不是已確認的網路事件編號。掃描沒有捕捉 heap 與可寫全域值，不能據此斷言其他呼叫形式不存在。

額外比對 `partySize`、`player_count`、`num_players`、`MissionPlayerCount`、`numLobbyMembers`、`numSessionMembers` 與 `/lobby` 字串：前四者分別出現在配對偏好欄位、觀戰欄位、`HiveMindComponent` 相關欄位及任務資料欄位附近；後三者則涉及欄位處理或路徑格式化。現有交叉引用沒有把任何一項連到上述房主加入上限或房間建立時的最大人數。故不將這些名稱當成可修改的容量設定。

磁碟 `game.dll` 的限定字串掃描未找到可直接識別容量的設定；離線載入映像捕捉中雖有前述 `lobby`／成員數字串，其交叉引用仍未連到容量判斷。`PlayFabMultiplayerWin.dll` 的 `MaxPlayers` 字串屬通用 SDK，沒有證據把它連到上述遊戲流程。字串有無皆不能證明網路路徑的行為。

## 八人實作所需的原生布局變更

後續[待處理記錄消費流程](pending_consumer_findings.json)將加入請求連到 `0x108a440`：它從四筆待處理記錄取資料，符合條件時轉入另一組四筆大型記錄並發出結構化通知。peer 清理函式 `0x108b6b0` 亦逐一處理這四筆大型記錄。這已建立加入、後續處理、清理之間的靜態關係。

| 已核對區域 | 現有位置（結尾不包含） | 保持起點與間距、直接擴至八筆的結果 |
|---|---|---|
| peer 記錄 | `+0x20..+0x100`，四筆、間距 `0x38` | 結尾變成 `+0x1e0`，侵入索引旗標及大型記錄。 |
| 索引旗標 | `+0x100..+0x104`，四個位元組 | 分配器目前只分配 `0..3`；索引存於 peer 記錄的 32 位元欄位 `+0x14`。 |
| 大型記錄 | `+0x108..+0x808`，四筆、間距 `0x1c0` | 結尾變成 `+0xf08`，侵入待處理記錄及後方資料。 |
| 待處理記錄 | `+0x808..+0x908`，四筆、間距 `0x40` | 結尾變成 `+0xa08`，覆蓋仍使用的 `+0x908`／`+0x910` 兩個 qword，並跨入下一個子物件。 |

這些物件不是互相獨立的可調整陣列。[外層初始化](host_owner_init_disasm.json)直接在外層物件 `+0x159b0` 建立房主子物件，並在 `+0x162c8` 初始化另一個子物件；兩者起點相距 `0x918`。[開始主持流程](hosting_init_disasm.json)會按目前布局清理四筆 peer 記錄、重設索引旗標，並清零 `+0x108` 起的 `0x700` bytes。原生擴容必須重新配置儲存空間，並更新初始化、加入、後續處理、釋放、遷移與直接存取位置。

[註冊函式](host_event_registration_disasm.json) `0xb2afb0` 還把同一房主物件指標及 `0xEC` 標籤加入 18 個不同登錄表。其一使用 `+0x66f0` 計數、`+0x66f8` 指標與 `+0x6700` 標籤，與已知加入呼叫的讀取位置吻合。因此若搬移整個房主物件，也必須維持這些已註冊指標的正確性。這裡的 18 是函式中加入登錄表的次數，並非可容納玩家數。

新增的[函式候選掃描工具](tools/layout_inventory.py)從 `HostSynchronizer` 字串的 84 個有效引用整理出 [40 個候選函式](host_layout_inventory.json)，涵蓋開始主持、遷移、連線準備、移除玩家與任務切換。[欄位引用工具](tools/field_refs.py)另找出[外層內嵌區域的引用](host_embedded_region_refs.json)。這些清單仍含其他物件使用相同偏移的情況，不能直接當成完整修改點清單；需要逐一核對基底指標。

本輪[搬移引用核對](host_relocation_inventory.json)已對其中 9 條根函式路徑建立基底來源，固定 100 個指令位置並重播其 bytes、指令邊界與 unwind root。除了初始化及更新函式直接計算 `owner+0x159b0`，客戶端流程 `0x1083150`／`0x10845b0` 還會經自身第一個 qword 取回 owner，再直接寫 `owner+0x159c8`，即房主 `+0x18` 狀態。`host+0` 本身是 owner 的回指，也不能直接替換成擴充陣列的指標。這證明搬移需要更新多條直接存取路徑；100 個位置仍只是已核對子集，未涵蓋全部動態、計算位址及其他 helper。

後續[房主生命週期盤點](host_expansion_inventory.json)按讀寫種類與作用欄位固定 11 組、104 項指令記錄，涵蓋 103 個不同位置。開始主持及主機遷移都會清四筆 peer、四個索引旗標，並從 `+0x108` 清固定 `0x700` bytes。移除流程逐一處理四個大型記錄；清除某筆大型記錄時，程式先清零 stack 暫存，再複製回該記錄。遷移使用的空 peer helper `0x108b520` 只查四槽，滿時回傳零；呼叫端其後直接寫返回位址，依賴空槽存在的條件。擴容需要一併更新清理、重建、索引與空槽尋找，才能維持這些條件。

玩家索引的已知本機儲存寬度為 32 位元；[協定與索引記錄](protocol_index_and_wire_notes.md)又將房主欄位連到事件雜湊 `0x4804fcf4` 的 4-byte 傳輸描述欄位。另找到五欄位接收回呼候選，欄位形狀與發送端吻合，並寫入客戶端 peer 記錄；但**該事件雜湊到此回呼的執行期註冊關係尚未閉合**，故不能稱為已證完整傳輸鏈。實際封包編碼、解碼端限制與玩家實體生成上限亦未確認。

本輪[本地／遠端分派對照](protocol_host_to_client_dispatch.json)找到更強的語意關係：同一分支對本地成員在 `0x108c960` 直接呼叫 `0xb90b20`，對遠端成員在 `0x108c97b` 以相同五項參數呼叫發送函式 `0xbe4910`。候選接收 wrapper `0xbaba80` 也直接呼叫 `0xb90b20`。這支持兩者是同一通知的本地與遠端處理路徑，但仍未直接讀到 hash→callback 的註冊映射。[靜態函式指標連續區](rpc_binding_callback_table.json)內可見該 wrapper，位於 592 個指標中的零起算索引 168；這個索引不是已驗證的 wire event ID，該區也沒有對應 hash。

客戶端也有獨立的布局問題：peer 陣列從 `client+0xd0` 開始、間距 `0x20`；重設流程清理 `0x80` bytes，即四筆記錄。其後的 `client+0x150` 由初始化流程寫入既有資料。如果保持現有布局，第五筆 append 的起點恰為 `+0x150`。因此原生八人擴容需同時處理房主與客戶端儲存空間，僅修改房主容量無法構成可用實作。上述分析沒有執行第五人連線，不能證明這些分支在修改後的執行期行為。

[客戶端擴容盤點](client_expansion_notes.md)又核對了四組相鄰清單及 94 個指令錨點：

| count 欄位 | 清單起點／間距 | 下一個已使用欄位 | 現有可容納筆數 |
|---|---|---|---:|
| `+0x10` | `+0x18`／`8` bytes | `+0x38` | 4 |
| `+0x38` | `+0x40`／`0x10` bytes | `+0x80` | 4 |
| `+0x80` | `+0x88`／`0x10` bytes | `+0xc8` | 4 |
| `+0xc8` | `+0xd0`／`0x20` bytes | `+0x150` | 4 |

append、整筆 swap/remove 及重設前逐筆處理本身使用 count 算式，但兩條重設路徑都只清 `+0xd0` 起的 `0x80` bytes；`+0x88` 及 `+0x150` 的搜尋也有固定四筆迴圈。是否能沿用那些 count 算式，取決於四組清單均已有足夠空間，不能只擴最後一組。最初在限定的 client 候選函式內，`record+0x14` 只確認兩處純量寫入；後續擴大至外層 owner 的引用，已找到真正讀取端。

### 玩家索引的外層直接讀取及新限制

[索引消費者續查](client_index_consumers_findings.zh-TW.md)核對 `client = owner+0x162c8`，因此 player index 是 `owner+0x163ac+i*0x20`。全捕捉 code 的位移掃描找到 64 個指令、49 個 root 候選；其中已核實的來源均回到同一 owner global `0x347cef0`，不能把全部同位移命中都視為同一物件。新證據的 118 個 unwind 指令及一個有直接 caller 的 17 指令 leaf 已獨立核對。

- `0x6311c8` 讀到的 network index 被用於另一系統 `global[0x3326ae0]+0xc4a0+index*24` 的儲存尋址；最初尚未確認容量，後續已核對其四筆布局及相鄰有效資料，見下節。
- `0xb90143` 以 network index 查另一張 `+0x27d8` 映射表，要求**映射結果**小於四，再以該結果選取其他記錄。後續已確認此映射屬於裝備選擇畫面，不能把 network index 或畫面槽位直接等同 gameplay roster ordinal。
- `0x1086460` 對本地 ID 對應記錄的 network index 直接比較四；索引 `4..7` 會跳過一條後續呼叫 roster 方法的特殊路徑。尚未證明這等於整個第五人加入失敗，但它是擴容時必須核實的獨立限制。

因此索引的儲存寬度足夠並不代表使用它的陣列或映射已支援八筆。後續配置、容量及生命週期核對如下。

### 索引下游的數值彙整系統同樣只有四筆

[24-byte 儲存容量續查](index_storage_capacity_findings.zh-TW.md)已核對 247 個指令位置，將 `global[0x3326ae0]` 連到 `owner+0x7c7368` 的 tag `0x73` 物件。network index 暫存 `+0xc4a0` 只有四筆，結尾 `+0xc500` 已是實際使用的型別化資料區；第五筆 ID 會覆蓋該區的 key／integer 欄位。另一組 `+0xc440` 四筆彙整結果、固定 96-byte 清除、四筆搜尋及四項展開加總也已確認。

此系統另有三個 `count+1<=4` 的加入實作、四筆物件指標及四筆 40-byte 記錄，最後一筆記錄結尾正好接上下一個 owner 子物件。其網路序列化、移動／重排、owner 初始化與 tag 登錄已找到具體讀寫路徑；後續[元件容量核對](player_component_capacity_findings.zh-TW.md)又把 `0x53e1b0` 接上元件 **226** 的靜態 callback slot 與參考 player 清單。正式業務名稱、實際載入清單及 runtime 派發仍未確認，不把它直接命名為樣本、獎勵或結算系統。這是八人擴容所需處理的另一個原生子系統。

### 裝備選擇畫面的四槽映射、資料與 UI 元件

[槽位映射續查](index_slot_mapping_findings.zh-TW.md)已核對 226 個不同指令位置。`MenuScreenLoadout.on_enter` 將同一畫面物件以 tag `0xe5` 登錄到已知事件清單，直接閉合先前未知物件的身分。`+0x27d8` 是 network index→畫面槽位表，`+0x27e8` 為反向表，各四個 DWORD；本地玩家固定映射至畫面槽位零，其餘槽位為一至三。

同一畫面還有四筆 `0x9f0` 的 network-index 資料、四個 `0x1ee18` 的大型 UI 元件、固定四筆的初始化／清除／切換流程。第五筆資料、第五個映射或第五個 UI 元件都會侵入已使用的相鄰區域。畫面更新另在 roster ordinal≥4 時進入錯誤呼叫後的 `int3` 路徑；另一資料更新也明確要求 network index<4。擴容需要一併處理畫面的資料、雙向映射、UI 元件及堆疊暫存，不能僅改顯示人數，也不能將這個畫面限制當成底層角色分配器容量。

## 玩家實體追查與復活更新的四項限制

### 本地加入同步可繼續，但索引 4–7 會略過 player 建立

[完整正常流程分析](local_player_creation_gate_findings.zh-TW.md)將 `0x1085d70` 連到明確日誌 `ClientSynchronizer/from_host_added_to_session`，解析六段相連 unwind fragments 的 565 條指令。History／loadout 準備分支都先合流，再用本地 peer ID 查 confirmed-peer 記錄，取其中的 **network index** 與 4 作 unsigned 比較。

`0x1086469` 的通過邊 `→0x108646f` 是該 root 到達 `0x10868bf` handle 呼叫及 `0x10868d7` player-hash `FDC140` 呼叫的必要路徑；移除此邊後兩者均不可達。索引≥4、空表或查無 peer 都進 `0x108624d` fallback，寫入另一個 32 筆 ring 的 type 3 記錄，再進共同 peer 同步尾部。該 ring 的 consumer 尚未具名；不能稱為特定 UI 錯誤。兩條路徑都可到達檢查「全部 peer 同步後向 host 報 ready」的 helper，**可到達不代表一定送出 ready，更不代表 player 已建立**。

保留這條正常加入路徑時，必須讓有效 network index 4–7 進入等效 player 建立，或提供經驗證的替代路徑；只提高 host／client 計數會留下這項障礙。這不是全遊戲不存在其他建立入口的證明，亦不能無條件刪除 guard：未找到記錄及 sentinel 仍需處理，下游元件儲存亦須同步擴容。程式與 CFG 的[獨立審查](local_player_creation_gate_review.zh-TW.md)另從原始 capture 重建並核對。

[加入後續與復活更新補充](player_spawn_findings.zh-TW.md)核對了客戶端 append 後的 `0xb5ea90` 呼叫：傳入的是 peer identifier，並非剛存入記錄 `+0x14` 的 player index。已追到的分支會傳送／同步資料，尚未閉合到 player entity 的分配器。因此不能把這個呼叫當成第五名玩家建角成功的依據。

另在實際 gameplay 更新找到獨立的四項限制：game-state 值為 `4` 的分支呼叫 `0xacbe60`，其中建立並排序四個候選，序號固定為 `0..3`；之後恰好循環四次，按序號讀 roster 的 `+0xe8+8*i` player 狀態物件。雖然它會先與 roster `+0x84` 的動態 count 比較，即使 count 大於四，這段也沒有序號 `4` 的候選。相關狀態分支包含復活計時及出生狀態處理，後續 `0xac7be0` 計算位置並發出結構化事件。

這是**特定 gameplay／復活更新流程的四項處理上限**。目前未證明所有玩家都必經此路徑、這些 roster 序號等同網路 player index，或 player entity 配置器本身只有四格。最初分析的逐指令及 game-state jump table 證據保存在 [player_spawn_evidence.json](player_spawn_evidence.json)，可用 `player_spawn_replay.py` 由固定捕捉重播；後续接收及 handle 產生路徑已補充如下。

### 出生位置接收、等待狀態與角色 handle 的新連結

[出生事件續查](respawn_receiver_findings.zh-TW.md)固定並核對 216 個指令位置。`0xac7be0` 先直接呼叫 `0xac83f0`，再透過 `0xbe1920` 發送 hash `0x280728d6` 的六欄位事件；接收 wrapper `0xba7390` 經 `0xb8e970` 也將同型六欄位交給 `0xac83f0`。這建立了本地／遠端處理的強語義對照，runtime hash→wrapper 登錄仍未直接觀察。

`0xac83f0` 以 player object ID 查 roster 中的 ordinal，將位置寫入 `0x70` 記錄，再由 `0x608a90` 將 `0x38` 記錄狀態設為 `2`。分支與日誌字串對應 **2 = WaitingForRespawnTimer、3 = Spawned**。後續更新要求 **ordinal 0、player 物件 `+0x14` bit 0 置位**及等待條件；該 bit 的「本機」語義仍是推論，不據此把所有玩家視為同一條生成路徑。

符合條件後，`0xac8800` 讀取出生資料，在 `0xac9c19` 經 `api+0xc0 → 物件首指標 → 表+0x18` 呼叫引擎介面；返回的 32-bit handle 交給 `0x607820`，將同一 player ID 的狀態設為 `3`，並寫到 `roster+ordinal*0x70+0x108`。這把玩法更新追到 handle 產生及名單寫回的具體邊界。第三次擷取已將引擎目標定位為 `EXE+0x30ff50`，其內部直接呼叫 `EXE+0x1ae380`；內部分配容量及實際成功結果仍未知，不能把 ordinal 0 的分支直接改成八次無條件生成。

前述 client index `<4` 路徑亦會呼叫 roster 的 `0x608b60`，但其後續用途不同，未直接進入本節的 `0x607820/0x608a90` 寫回流程；不能把該 index 比較直接稱為此角色分配器的四人上限。

### handle 產生之後仍有資源與回呼分派

[資源名稱與後續分派核對](spawn_resource_identity_findings.zh-TW.md)使用固定 FileDiver 演算法及名稱表，重算出三個完整 64-bit 雜湊匹配。兩個初始間接呼叫都使用與 `content/entities/dummy` 相符的值；返回 handle 之後，同一 helper `0xfdc140` 分別接收與 `content/entities/player`、`content/fac_helldivers/cha_avatar/avatar_helldiver` 相符的另一個雜湊。

該 helper 把資源雜湊與 handle 寫入同一筆記錄，之後進入 `0x581320/0x581780` 的索引清單與回呼表分派。91 個指令位置及三個雜湊均已獨立重播核對。這確認了「取得 handle，再關聯資源並分派處理」的兩步資料流；名稱表未證明目前安裝資產的全部內容，也沒有觀察建立成功或證明第二步建立另一個實體。最初尚未找到實際 roster callback；後續已補上元件 239 的靜態登錄與参考清單，見下節。完整角色建立的執行結果仍未驗證。

### 元件 239：資源清單、名單插入與屬性建立

[Callback 登錄續查](spawn_callback_registration_findings.zh-TW.md)找到先前 unwind 篩選略過的 leaf 初始化函式 `0x556d90`。其入口由 `0x568239` 的直接 call 證明；全段 29,779 bytes 為 2,127 組函式位址載入／寫表指令，另加一個返回。主代理另用固定 14-byte 指令對重算全部 2,127 個唯一目的位移，與重播結果一致。元件 **239** 在三張已知派發表分別登錄：

| 相對 callback owner 的表起點 | 元件 239 目標 | 已核對行為 |
|---|---|---|
| `+0xf0c110` | `0x540920` | 四筆 roster 插入限制。 |
| `+0xf0cb30` | `0x540ae0 → 0x60c640` | 產生屬性並初始化 roster 的 `0x20` 平行記錄。 |
| `+0xf0d550` | `0x540b10 → 0x6054f0` | 後續處理，會讀取同一記錄的 `index` 欄位。 |

建構與派發都以原 context `+0x40` 作 callback owner，原 context 又發布到 global `0x346bf98`，與 metadata reader 的來源接上。這是靜態表初始化，不代表已觀察執行或排除初始化後被改寫。

[資源 metadata 核對](spawn_resource_metadata_findings.zh-TW.md)完整解析固定 FileDiver 明文快照的 272 個 instance 與 1,909 個非空資源鍵：`player` 有九個元件 `[3,33,41,43,226,238,239,250,260]`，`dummy` 只含 88，`avatar_helldiver` 的 49 個元件不含 239。111 個指令位置另連到 `generated_entities.dl_bin` 檔名、metadata 欄位與索引清單讀者。**這些清單來自參考資產；目前安裝的加密檔解密後等同性及 runtime 清單仍未知。** 不能據此把 player 與 avatar 的兩條建立流程合併成同一個角色配置器。

[屬性與索引橋接](roster_component_binding_findings.zh-TW.md)則確認：`0x60c640 → 0x134f190` 用本地 peer ID 查 confirmed-peer 記錄，取得 network index，寫到 `roster+ordinal*0x20+0x3b4`，再輸出名為 `index` 的屬性 descriptor。這把 network index 與 roster 內的欄位接起來，沒有證明它等於 roster ordinal。屬性階段只在 creation params 首 byte 非零時執行；該 byte 亦是新 entity `+0x14` bit 0 的 producer，而已知本地 player 建立路徑會傳 1。八個 descriptor 是單一 entity 的八個欄位，不是八位玩家。

後續 `0x6054f0` 有一個可具體分類的 `<4` 讀者：index 0–3 讀四筆 16-byte 色盤，三個分量乘 255 得到四組 RGB 形狀的值；index 4–7 走既有替代分支，輸出 `(255,255,255)` 並繼續執行，沒有越界讀此表或在此拒絕加入。因此這處可以先保留替代值，無須作為八人加入的必要改動。精確顯示端／控制器用途尚未具名確認。稍後另一個間接呼叫把 `player_count` 字串及 `roster+0x84` 實際筆數交給引擎；此 caller 未截為四，但 callee 的接受範圍仍未知。

本輪交付核對：callback 證據 v2 的 82 個選定指令位置及完整 2,127 組初始化寫入，屬性證據 v3 的 218 個指令位置與色盤／字串，均由主代理從固定原始 capture 獨立核對。資產 parser 的 111 個指令位置、兩個字串及完整參考檔解析，另由獨立代理用不同解析方法核對。這些是離線證據驗證，不是八人 Mod 測試。

### 同一參考 player 清單中，另外五個元件也限制四筆

[九個元件的完整入口核對](player_component_capacity_findings.zh-TW.md)重新驗證 callback initializer 及九個第一階段入口，共 428 條指令。元件 **33、41、43、226、238、239、250** 都有 `count+1<=4`，否則執行寫零位址的分支；有 creation params 分類者，護欄在分類之前。226 與 239 是先前已知的 tag `0x73` 及 roster，其餘五個是本次新增。

| 新確認元件 | 原布局的擴容衝突，索引均為零起算儲存位置 |
|---|---|
| 33 | 初次分析確認指標槽位 5 覆蓋 `+0x98` 記錄；後續生命週期已證明槽位 4 的 `[+0x90,+0x98)` 也會覆蓋 `+0x90..+0x93` 的逐 ordinal bytes。 |
| 41 | 指標槽位 4 覆蓋 `+0x88` 大記錄 0；大記錄槽位 4 又恰好落在另一組 `+0x26528` 記錄。 |
| 43 | 指標槽位 4 覆蓋 `+0x88` 記錄 0。 |
| 238 | 指標槽位 4 範圍 `[+0x968,+0x970)` 覆蓋 `+0x96c` 記錄的前四個 bytes。 |
| 250 | 指標槽位 4 覆蓋 `+0x90` 記錄 0。 |

分類插入可能先搬移舊資料，不能將「第五次呼叫」直接等同「此次寫槽位 4」。41 的大記錄及 250 的輔助記錄清零還取決於 creation params 首 byte，但指標寫入位於分支合流後。上述靜態登錄與參考資產清單的界限仍適用；[獨立審查](player_component_capacity_review.zh-TW.md)已核對各入口、七個護欄及重疊計算。元件 3 與 260 原先只有容量欄位及 helper 線索，後續已補上初始化與擴容，見下節。

### 剩餘兩個元件：已具備大於八筆的動態儲存

九個參考 player 元件的容量分類現在可具體區分為七個固定四筆與兩個動態配置元件：

| 元件 | 已核對的資料容量 | 對八槽方案的決策 |
|---|---|---|
| 33、41、43、226、238、239、250 | 已登錄加入 callback 有四筆護欄；多組內嵌陣列只有四筆 | 必須共同處理 guard、資料空間及全部相關讀寫／生命週期。 |
| [3／TagComponentData](component3_capacity_findings.zh-TW.md) | 初始 512 筆兩個 qword 陣列、1,024 個 map buckets；資料滿時增加 256，map 獨立擴容 | 已核對的路徑沒有四筆容量改八的需求，保留既有動態儲存。 |
| [260／WeatheringComponentData](component260_capacity_findings.zh-TW.md) | 初始 64 筆四個資料陣列、128 個 map buckets；資料滿時增加 32，map 獨立擴容 | 已核對的配置、加入、搬移及 property 接收可容納 ordinal0–7，不需為八槽重排其 header。 |

3 的物件是 `owner+E8`，260 是 `owner+EB5E10`；兩者資料均經獨立配置的 pointer 存取，未把資料陣列內嵌在下一個 owner 成員之前。這些容量屬於所有 component entities，不能稱為玩家專屬名額。結論以配置成功、有效 entity／ordinal 為前提；外部配置介面、當前佔用量與全部下游仍未執行驗證。

元件 260 的身分鏈也補上前一輪 property 分派最後一段的未知項：`BD1DE4/BD1DF2` 的 `owner+EB5E10 → 799790` 與 index260 的 callback global `3326A50` 確定是同一物件。已保存完整初始化、四陣列擴容、壓實與分類轉移；分類增加對第二個 qword 陣列清零目的槽，分類減少則交換，沒有將所有搬移簡化為同一操作。

### 新增五個元件的生命週期與外層布局

續查以已登錄 callback、完整 helper 與同一 owner 來源為依據，補出原先只看 append 看不到的資料。下表位移均相對各元件 S，O 為 component owner：

| 元件 | 本輪新增確認 | 下一個已發布成員的邊界 |
|---|---|---|
| [33](component33_250_lifecycle_findings.zh-TW.md) | `+0x90` 是逐 ordinal byte；另有 `+0x1d8` 的四筆 `0x38` 記錄。Tag `0x7c` 保存兩份 registry pointer。 | S=O+`0x3ca0`；四筆第二組記錄結束於 S+`0x2b8`，等於 O+`0x3f58`。 |
| [41](component41_lifecycle_findings.zh-TW.md) | 除大記錄與第一組小記錄，另有 `+0x26688` 的四筆 `0x58` 屬性記錄；有建立／套用及更新資料流。Tag `0x80` 保存五份 pointer。 | S=O+`0x4148`；第三組記錄結束於 S+`0x267e8`，等於 O+`0x2a930`。 |
| [43](component43_lifecycle_findings.zh-TW.md) | `0x9ba8d0` 單向壓實整筆 `0x108` 與 entity pointer，再修 map；owner 更新與 count 複製繞過元件 global。 | S=O+`0x2a988`；記錄結束於 S+`0x4a8`，等於 O+`0x2ae30`。 |
| [238](component238_lifecycle_findings.zh-TW.md) | `+0x968` 的逐 ordinal byte、`+0xa7c` 的四筆 `0x40` property 記錄；有初始化、反序列化及分類轉移。Tag `0x18` 保存七份 pointer。 | S=O+`0xe9fc98`；property 結束 S+`0xb7c`，再四 bytes 即 O+`0xea0818` 的 roster。 |
| [250](component33_250_lifecycle_findings.zh-TW.md) | `+0x160`、`+0x164` 是兩組逐 ordinal bytes，搬移規則不同。Tag `0x7f` 保存八份 pointer。 | S=O+`0xeb5178`；第二組 bytes 結束於 S+`0x168`，等於 O+`0xeb52e0`。 |

所有五個元件都有 owner 直接取址路徑；數個元件亦將指標保存於 registry，取消登錄仍按原位址比對。整物件搬移需要共同修正這些別名，以及指向自身 inline hash buckets 的指標。若保留 S 及 header、另移陣列，則仍需完整改接固定 offset 與衍生地址的陣列讀写。

搬移語義已有可操作的區分：單向壓實會複製資料及修正 ID→ordinal，分類轉移則可能交換部分記錄、清零目的記錄，或只單向複製某個 byte。特別是 250，分類增加清零目的 `0x34` record，分類減少才交換；`+0x160` byte 單向複製，`+0x164` byte 交換。獨立審查已促成正式 v2 修正，沒有將兩組 bytes 或所有轉移合併成一個通用 swap。

八個 inline hash buckets 是另一種容量；共用 insertion／deletion 以 bucket 數作有界探測，沒有另外的四筆負載條件，也沒有自動增容。[後續離線語義驗證](component_map_capacity_findings.zh-TW.md)已核對固定 `172F790/172F8A0` bytes，建立 32-bit 模型與限定指令直譯器：65,536 種八筆 key 的 home 分布、80,640 種完整刪除順序，以及 4,506 次模型／指令對照均通過，主代理獨立重播逐 byte 一致。

在有效 key、正確 sentinel、非零且為 2 的整數次冪 capacity、足夠 backing 及無並行修改等前提下，模型支持八項滿載、刪除、重插及更新既有 ordinal，沒有發現必須一律改十六 buckets 的要求。**滿表新增第九個不同 key 沒有安全失敗返回，首次會嘗試向地址 `0x4` 寫入。** 因此保留八 buckets 的方案必須維持不同有效 key 不超過八，並維持外層資料陣列範圍。這是 Python 模型與保存指令的核對，未執行遊戲函式或八人玩法；lookup 與 map 的 invalid 值來源不同，模型假設也已明列。

這批證據與[設計稿](PLAYER_COMPONENT_RELOCATION_PLAN.zh-TW.md)將工作收束到完整陣列存取；下節已補上選定 property 分派。另在元件 43 的大型 consumer `129FD00` 找到[內嵌更新](component43_inline_consumer_findings.zh-TW.md)：`12A02BB` 取 S 後直接使用 pointer `+68`、record `+88` 與每筆 count `+188`，不經 `9BA430`。只改接共用 helper 會漏掉它。有限 RIP MOV／LEA 掃描識別的十個 global 引用都已分類，但其他別名與編碼仍未窮盡；目前仍不是可直接套用的完整 relocation manifest。

### 元件 239 的其餘 callback：重排保留 network index

[剩餘回呼與生命週期](roster_property_apply_findings.zh-TW.md)將五個目標分為移除前清理、前段移入／移出、空回呼及 `disconnected=true` 通知。當時未由這些目標找到反序列化入口；本次已從另一條 property 分派定位 `BD13B3 → 60C890`，見下節。

`0x60cf50/0x60d300` 改變 roster ordinal 時會搬移完整 `0x20` bytes 屬性記錄，使其中 `+0xc` 的 network index 保持與同一 entity 關聯，並另外修正 ID→ordinal 雜湊值。兩者會操作四組平行儲存；移入方向清零目的 `0x70` bytes 狀態，移出方向才完整交換該狀態，不能合併成相同的 swap 行為。擴容需涵蓋直接位移及 `lea` 衍生的別名存取。

順序也已確認：移入時先設定 entity `+0x14` bit 0；移出時先發通知、搬移，返回後才清 bit 0。刪除流程先執行 `540b20→605950` 清理，再由另一張 callback 表執行 `540a40` 實際 roster 移除。主代理獨立核對正式 v3 證據的 379 個不同指令位置（含登錄及短 leaf）、八個根的 fragment SHA 與通知字串；這些結果補齊布局變更需要保留的生命週期規則，並未驗證八人執行。

### 直接用 network index 寫入的玩法四槽儲存

[索引下游核對](roster_index_usage_findings.zh-TW.md)另找到確定的布局衝突：除錯名稱關聯為 `StateGame`、tag `0xb5` 的父物件 P，經同一 registry 派發後將 `S=P+0x50` 傳給 `0xffd8c0`，形成 tag `0xda` 子物件。S 內有 `+0x80` 起的四筆 `0x90` 記錄，以及 `+0x70` 起的四個平行 DWORD。

`0xffe3ff` 從已確認的 roster `+ordinal*0x20+0x3b4` 讀 network index，隨後四次寫入直接以它作下標，沒有 `<4` 護欄。若該區塊以 index 4 執行，會精確写到 **P `+0x318/+0x319/+0x31c/+0x320`**，前者是實際使用的 qword，後者為 16-byte bitset。這是有同一父子物件來源支持的靜態衝突，尚未在第五位玩家身上觀察到執行。

把初始化循環改成八次也不夠：主陣列會侵入父物件欄位，平行 DWORD 陣列會碰主陣列第一筆；兩組儲存必須一起重排。其他同來源讀者已分清：`0xacf420` 對 index≥4 返回 false，但不是已證明的加入拒絕；`0xacf1f0` 回傳預設向量；一處 32-bit mask consumer 容得下 bits 4–7，其 producer 未核實；純量 index getter 沒有四人截斷。

原先容量未知的 `0x7275d6 → 0x14335f0` 已由[雙 float 儲存續查](indexed_float_storage_findings.zh-TW.md)接到同一物件 D 的 initializer／cleanup。初始化只建立 `[D+80E18,D+81878)` 四筆、每筆 `0x298` bytes；writer 以 network index n 寫入 `D+80E24+n*298` 的八 bytes，沒有前置 `<4` 檢查。n=4 寫 `[81884,8188C)`，其中四 bytes 覆蓋下一個 `D+81888` 子物件首 qword；n=7 寫 `[8204C,82054)`，覆蓋另一子物件兩個有清理 reader 的索引欄位。這是條件式地址衝突，未觀察第五人觸發或實際錯誤症狀。D 的正式類別仍未知，不能僅因父 callback 有 Galaxy_map 字串就替它命名。

### 同一 float 物件的更新與暫存表也需擴容

[有限 consumer 續查](indexed_float_consumers_findings.zh-TW.md)以相同 manager／D 來源接上 12 個 roots，補齊已選路徑的初始化、清理、掃描、動態索引讀寫與相鄰 metadata。已確認的必要修改包括：

| 儲存或路徑 | 固定版本的行為 | 對八槽方案的要求 |
|---|---|---|
| 四筆 `0x298` records | 多個更新／cleanup 固定四筆；每筆另有五個子物件 | 新空間需同步改接初始化、讀寫、子物件方法與清理，保留 owner／pool 指標關係。 |
| `14329B0` | 每次處理兩筆，兩次迭代，按條件寫回 float pairs | 八筆等價遍歷需四次雙筆迭代並改接起點；僅修改其他地方的 `cmp 4` 會漏掉此處。 |
| `D+8D6C4`、`D+8D6D4` | 各四個 DWORD；第一表 index 4 侵入第二表，第二表 index 4 侵入已使用的 qword 狀態 | 兩表都需擴大／搬移，涵蓋初始化及 `142FF90/142FED0/1430450` 存取。 |
| `142D870` stack map | `[RBP-60,RBP-50)` 只有四格；以 roster network index 直接寫入 rank | n=4 未被 local/current 條件跳過時覆蓋 `RBP-50`；需重新安排暫存空間及索引界限。 |
| 三張 rank→ID 表 | 各只初始化三項；map 結果作下標，ID 之後交给其他 lookup | 需確認新增 ID 或有界 fallback；現有資料沒有給出可直接填入的額外 ID。 |

Stack 衝突有具體讀寫證據：`142EB33` 把 `RBP-50` 初始化為 `56D7E815`，`142EB7D` 在 n=4 時覆寫同一位置，`142ED3B` 隨後可能把它作為 ID 讀取。這是固定程式的條件式資料流結論，沒有聲稱已觀察到第五人觸發或特定崩潰。

八筆 roster 若包含會被跳過的有效 selected local/current index，其他條目最多七項；但 `142EA4E` 允許 selected index=-1，八個有效 n=0..7 此時全部保留，rank 可達 7。因此七項 ID 表只能在前述條件成立時使用；缺 local 的情況需受界限保護的處理，不能靠七格容量涵蓋。

已選roots的正常控制流、register重用及referenced switch table都納入重播和獨立核對；這不是全部consumer的完整集合。當時未閉合的外部q、部分interior-object helpers與ID用途已在下節續查；其他caller、執行期資源及完整改接仍有邊界，尚不足以生成可載入的補丁。

### 後續閉合：host 索引、子物件資源池與音效 ID

[外部 q 來源](indexed_float_external_index_findings.zh-TW.md)已接上同一owner global `347CEF0`。程式用 `owner+B3A8` 的host-selection peer key查confirmed-peer記錄，再取`record+14`的32-bit network index。它與用`B398`查找的本機index不同，也不能拿表內ordinal取代。Host migration會保留既有index，故不能一律把q視為0。這條讀者沒有額外`q<4`比較；改接client表及D records時，須包含它的owner-relative取址及兩個float讀取，保留找不到記錄／sentinel的行為。

[五個子物件的生命週期](indexed_float_subobjects_findings.zh-TW.md)確認實際constructor為`140C160`。每個子物件S持有最多12個node索引，指向共用pool `P=D+36F8`；node存有D、外部context與template指標。新增四筆record的20個S必須fresh-initialize；複製active S會共享相同node，清理一份後另一份仍可能引用已清除的資源。搬移原四筆則需要唯一所有權轉移，以及所有caller/alias改接。

Pool有256個`0x208`-byte nodes，從`D+3718`到`D+23F18`，後者正是occupancy區起點；它還被D的其他子物件共用。新增20個S的索引欄位最多可表示240個node參照，全部八筆的40個S最多480個，前提是合法template count不超過12。**這不是實際需求或池一定耗盡的測量**，但已確立不能直接假設256足夠，也不能只改capacity後原地加長。

[後續模板重播](indexed_float_template_budget_findings.zh-TW.md)把指定模板的需求進一步限定為每筆11格、新增四筆44格、八筆88格；四種模板是`17/18/19/1B`，各加入`5/1/3/1`個nodes，五個S中`1B`使用兩次。保留256格時，其他用途與切換期間的額外占用須合計不超過168格。33個合成案例、原bytes核對與同來源重跑通過；執行期模板內容、其他writer與pool占用仍未觀察。

配置函式`140C2E0`在配置前先保存requested template ID，池滿時保留已配置部分並返回；下次相同ID會入口早退，不自動補齊。因此原生方案還需確認上述模板等同性、其他共用池需求與失敗處理，並保持cleanup期間D及其resource context有效。

[外層初始清零證據](indexed_float_pool_initial_zero_findings.zh-TW.md)核對6個完整roots及22項register來源關係，將global`3326340`的zeroed allocation接到`O → M → D → P`。k=0時P位於外層`+7ACE00`，occupancy為`+7CD620..7CD720`，都在首次整塊清零內。新增S若沿用active P應保留占用紀錄；不能將這條初始清零路徑套作每次擴容的reset。生命週期中的其他寫入與重用一致性仍待驗證。

[後續直接清單核對](indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)確認兩個完整roots中305個S的逐項建立／清理對應；八筆獨立儲存方案的兩份投影均325項。若各active node唯一屬於清單中的S、indices與occupancy／used count一致、context有效且沒有重入修改，這份清單能覆蓋其所屬nodes的回收。整池清空仍需排除清單之外的owner。Cleanup本地指令不重設cursor；capacity不變且cursor合法時，保留非零cursor不妨礙下次空位搜尋。

[Rank ID 的用途](indexed_float_rank_ids_findings.zh-TW.md)已由plugin初始化、`wwise_trigger_event` callback及相同API slot閉合到Wwise：前兩表是狀態開始／結束的event hash，第三表走同plugin的浮點參數API，精確匯出名仍未知。從選定boot資產取出的兩張map各有65,536 buckets、20,848有效key；六個event hash都存在，但`6E61441F/833E051C`兩個parameter key不在該表，原lookup回傳0。這不能推論runtime一定使用該資產、0是安全fallback，或已有七／八套獨立音效選項。額外rank的事件對應及音源隔離仍待設計／驗證。

另在[兩個helper本體](indexed_float_helper_boundaries_findings.zh-TW.md)確認：`142FA60`處理metadata中的物件編號／selector，`1432F10`接收兩個packed float。在D及其他欄位原址不變的方案下，兩者本體沒有直接的玩家record／metadata陣列位址要改接；caller的存取仍需修改。兩個相似位移候選`142F860/1433380`尚未取得同D的caller來源，沒有被提升為已證修改點。

本輪[核對記錄](indexed_float_remaining_review.zh-TW.md)區分了原bytes、完整root、獨立CFG及語義審閱範圍。原代理在交叉審查階段因用量限制停止，主代理接手核對已落檔證據；自寫的helper分析與資產擷取尚未取得另一代理完整語義審查。沒有用保存產物或重播成功宣称可安裝Mod。

### Property 接收與格式分派已接合

[Roster 接收端](roster_property_receive_findings.zh-TW.md)完整保存 `60C890` 的 303 bytes／72 指令。它以 entity ID 查 map 得 roster ordinal，把八個 DWORD 寫入 `S+ordinal*20+3A8..3C4`；第四個 DWORD 是 `index`，完整 32 bits 保留，沒有 clamp、mask 或四人截斷。這個值不負責選擇 roster record。故此處不需增加 index 位元寬度；需要改接八個目的 store、保留 map 與 cursor 規則，並涵蓋 caller 的 `owner+EA0818` 直接別名。

[上游分派](property_dispatch_findings.zh-TW.md)則確認 `BC2D30` 先從 API `+40` 介面取得 16-byte output：`+0` 為 payload pointer、`+8` 為 selector。Selector `3A7` 透過 RVA table 進入 `BD138C`，依序消耗以下片段；這是 API 輸出的格式選擇，尚未證為 wire header 或 reference component index。

| 接收目的 | 函式 | 此 entity 的消耗 bytes | 片段起點 |
|---|---|---:|---:|
| 元件 250 | `671860` | 4（只取其中一 byte） | `0x00` |
| roster／元件 239 | `60C890` | 32 | `0x04` |
| 元件 238 | `87BB30` | 64 | `0x24` |
| 元件 33 | `666590` | 56 | `0x64` |
| 元件 41 | `7AF610` | 88 | `0x9C` |
| 元件 260，owner+`EB5E10`（後續已補身分） | `799790` | 36 | `0xF4` |

合計 `0x118`、280 bytes；所以此格式的 network index 位於 payload `0x04+0x0C=0x10`。它描述一個 entity，未見內嵌四名玩家清單；selector 上限 `73E` 和四 byte 欄位寬度都不是玩家容量。是否在當前遊戲為 player 選中此格式、API 如何產生資料、傳輸及服務是否接受八人仍未驗證。

接收函式沒有安全的 map-miss／短 buffer 檢查；有效 entity→ordinal 和已配置的目的陣列仍是必要前提。上游 handle resolver 也沒有提供普遍有效性保證，因此不能把這些 findings 當成可對任意 handle 呼叫的 API。

主代理獨立核對本支線 v2 證據的 **523 條不同指令**、全部選定 block SHA 及三個字串。與上述三支線的交付核對彙整在[本輪離線驗證記錄](PLAYER_CAPACITY_VERIFICATION.zh-TW.md)。

### 續查已閉合到原生玩家清單的插入護欄

[玩家 roster 來源與插入分析](player_roster_findings.zh-TW.md)將 global RVA `0x3326468` 追到大型 owner 內嵌的 `+0xea0818` 子物件，並核對初始化、兩條插入函式及上述 gameplay 讀取的是同一組欄位。兩條插入函式 `0x60ca80`／`0x60cba0` 均先把 `+0x80` 計數加一，再與 `4` 比較；超限分支有寫入零位址的指令。這確立了**原生玩家清單的四筆插入護欄**，仍不能外推為實體 heap 或平台後端的容量。

指標槽位為 `+0xe8`、`+0xf0`、`+0xf8`、`+0x100`。第五筆起點 `+0x108` 已是另一組間距 `0x70` 的輔助記錄；因此改掉四人比較也不能保證第五筆安全。`+0x84` 計數及 `+0xe8+8*i` 指標正是前述復活更新的輸入。此物件 `+0x7c` 的最高計數又等於 owner `+0xea0894`，閉合到先前 `player capacity:4` 診斷輸出。這次結論建立於插入／讀取資料流，超出了最初僅有字串線索的階段。

[56 個固定指令位置](player_roster_evidence.json)已由原始捕捉獨立重播核對，包括 leaf 初始化函式的直接呼叫入口。尚未找到兩個插入函式的直接呼叫者；間接分派、索引與實體生成的完整路徑仍待查證。

[roster 生命週期續查](roster_lifecycle_findings.zh-TW.md)補出另外兩條同 global 的等價插入實作 `0x540850`／`0x540920`。共用搬移函式 `0x60c410`、壓實 `0x60cc70` 及移除路徑會同步操作四組平行陣列：四個指標 `+0xe8..+0x107`、四筆 `0x70` 記錄 `+0x108..+0x2c7`、四筆 `0x38` 記錄 `+0x2c8..+0x3a7`、四筆 `0x20` 記錄 `+0x3a8..+0x427`。下一個 owner 子物件恰在 roster `+0x428` 開始。

若只按相同順序重新排成八槽，這個區域會延伸至 `+0x768`，多出 `0x340` bytes，與後續 owner 成員衝突。這是儲存需求的推算，不是可直接套用的補丁。後續 callback initializer 已證明 `0x540850/0x540920` 的函式位址登錄；`0x60ca80/0x60cba0` 自己的另一條 dispatch 仍未知。tag `0x69` 是 roster 物件註冊，與 component index 239 的函式表是不同用途。

[roster 分派續查](roster_dispatch_findings.zh-TW.md)已把 tag `0x69` 註冊連到七組實際消費流程：它們從 registry 取回 roster 指標，直接使用 `+0xe8`、`+0x108`、`+0x2c8`、`+0x3a8` 等原布局欄位，或呼叫 roster 方法。這補上了物件註冊後的正向使用證據，亦說明只替換 roster 全域指標不足以完成搬移。四個插入與兩個移除入口均核實為獨立 unwind 根；其參數分成 RCX 與 RDX 兩組。新增元件登錄證據已定位 inline callback 的參數對應，不能因此讓不同 ABI 的 helper 共用未經轉換的 hook。

## 平台建立參數與本機列舉限制

[建立路徑重播](creation_path_findings.zh-TW.md)進一步找到 `start_hosting` 所呼叫的 `0x1091980`，及平台更新流程中的同型間接呼叫。程式先取設定的非零值或預設 `4`，再將此數加 `4` 傳為介面 `+0xa0` 方法的第一個整數參數，儲存返回的 handle。在預設分支中該參數因此為 `8`。後續兩次限定擷取已定位 EXE 目標，並取得與 PlayFab Party 配置吻合的參數資料流，詳見下文；**具名 SDK 綁定與服務回應仍未取得**，不能把它直接命名為八位玩家容量。

同一建立流程還先呼叫 `0x1091800`，經另外兩個介面方法將設定原值（零設定分支中為 `4`）作第二個整數參數；其返回 handle 存於 `owner+8`，而上述加四路徑存於 `owner+0`。這是不同 API 與不同返回欄位，不能只挑其中傳入 `8` 的一條便判定已具備八人平台房間。

後續更新流程 `0x10937a0` 與 helper `0x1092e60` 則明確將平台回傳人數截為 `4`，其他平台分支亦以容量 `4` 呼叫成員列舉介面。因此八人實作還需處理本機平台大廳列舉與其儲存資料。這是從程式碼核對出的另一層限制；仍未證明服務端接受或拒絕八名玩家。

[平台成員緩衝區續查](platform_member_layout_findings.zh-TW.md)進一步核對 87 個指令位置：ID 陣列從平台物件 `+0x1b58` 起，每筆 8 bytes；第五筆恰好覆蓋正在使用的 `+0x1b78` 結果欄位及 `+0x1b7c` 控制欄位。八筆則延伸到 `+0x1b98`，還會侵入其他既有設定。後續三段 count-driven 讀取亦使用這個陣列起點。主 owner 在 `+0x1d470` 內嵌一份平台物件，並直接初始化相鄰欄位；另一路經 `owner+0x171c8` 的子物件再取 `+0x1c00`，呼叫同一平台更新。擴容需要處理這些不同實例、讀寫位置及外層初始化，不能只提高列舉容量。

重播程式已在 [v3 證據](creation_path_evidence_v3.json)保存經指令邊界核對的指令與來源指紋。當時缺少設定指標 global RVA `0x3326340` 的內容，以及 global RVA `0x3326308` 提供的介面表與目標函式；後述單次唯讀觀測已補上設定 `+0x20` 及兩個指定函式目標。其他介面與服務回應仍未取得。

## 介面來源與剩餘資料缺口

[介面來源追查](interface_source_findings.json)已找到 global `0x3326308` 的寫入：`get_plugin_api` 匯出提供設定函式，該設定函式將傳入 callback 交給初始化流程；初始化在 `0x4edab3` 以數值 `31` 呼叫 callback，再把返回指標存入 `0x3326308`。因此其值取自執行期的外部提供者。原先固定捕捉沒有 callback 實作、返回物件、`+0xf8` 介面表或 `+0xa0` 目標，不能只依那份捕捉定位其真正實作。

公開的 [Autodesk SDK API 定義](https://github.com/AutodeskGames/stingray-plugin-api-samples/blob/e9d937a013e4aa1f25b6f7d9bdee0ca985455cfd/stingray_sdk/engine_plugin_api/plugin_api.h)將數值 `31` 定義為 `C_API_ID`，而 [ScriptApi 定義](https://github.com/AutodeskGames/stingray-plugin-api-samples/blob/e9d937a013e4aa1f25b6f7d9bdee0ca985455cfd/stingray_sdk/engine_plugin_api/plugin_c_api.h)中若干介面位置與本輪觀察相符。這提供跨版本對照線索，尚不足以確認 HD2 整套 ABI；公開版本也沒有列出本輪使用的 `+0xf8` 延伸介面。

磁碟 PE 可核對匯出名稱與 RVA，但該匯出區的磁碟程式位元組與載入後捕捉不同；本報告的反組譯依據是已固定的載入後捕捉。因此不能把本報告的 RVA 與指令內容直接當成可就地替換的磁碟內容。

已另備[限定唯讀介面工具與操作範圍](tools/INTERFACE_PROBE.zh-TW.md)，完成 9 項 mock 測試、程式指紋重播與獨立審查。使用者其後同意一次擷取並手動啟動 HD2；工具於香港時間 12:02:53 從 PID `39964` 完成[限定唯讀擷取](interface_probe_live_20260927_1.json)，共讀取 **17,224 bytes**。兩個磁碟檔案雜湊、載入 PE 資訊及兩處程式指紋在前後檢查都吻合；兩次模組列表相同，重讀的指定指標欄位也相同。這只驗證了本次限定讀取，並非完整程序或原子快照。

| 本次觀測路徑 | 實際值／目標 | 判讀範圍 |
|---|---|---|
| API `+0x30` 表的 `+0x18` | `helldivers2.exe` RVA `0x3494b0`，保存 256 bytes | 已定位先前傳入設定原值的其中一個介面方法。 |
| API `+0xf8` 表的 `+0xa0` | `helldivers2.exe` RVA `0x8c6730`，保存 256 bytes | 已定位先前傳入設定值加四的介面方法。 |
| 設定物件 `+0x20` | 32-bit 值 `0` | 已知靜態呼叫端對零採用預設四；本次沒有追蹤建立呼叫或服務回應。 |

第一次擷取把上述兩個未知目標定位到 EXE；前文「既有捕捉缺少」的描述仍適用原先的靜態捕捉。隨後已分析保存片段及磁碟 EXE，並透過另行授權的第二次擷取補上四個下游入口，結果見下節。**擷取成功不代表平台支援八人，也沒有驗證五至八人玩法。**

第一次擷取的兩段保存程式均已完成一層離線分析：

- [`+0x30/+0x18` 入口](interface_target_30_findings.zh-TW.md)將入口第一、第二整數參數的低 32 bits，分別放入 EXE `0x4acde0` 的第六、第七個參數槽；回傳值又傳給 `0x349110`。目標 `0x3494b0` 的磁碟位元組從首位元組就與已保存的載入程式不同，故兩個下游的磁碟資料不能直接當作執行時實作。
- [`+0xf8/+0xa0` 入口](interface_target_f8_findings.md)將第一個 32-bit 參數寫入返回物件的 `+0x20`，並以第二個整數參數轉交 `0x8e1370`。因此「設定加四」確有後續用途；當時尚未確認欄位及函式的實際業務語義。此入口、`0x8ccfa0` 與 `0x8e1370` 在 PE 虛擬區域內沒有對應磁碟原始 bytes，例外目錄也沒有磁碟原始內容。當時兩個下游尚未保存，第二次擷取已補上指定範圍，見下節。

上述入口均能在第一次保存的 256-byte 前綴內追至 `ret`；當時尚缺下游載入程式、呼叫結果及服務回應。這把下一階段的程式資料缺口縮小到具體 EXE 函式；仍不能由入口內沒有比較就判定下游接受八人。

### 第二次限定擷取：四個已定位的 EXE 函式

使用者另外同意四個固定 EXE 函式的唯讀擷取後，[第二階段工具](tools/ENGINE_CALLEE_PROBE.zh-TW.md)於香港時間 12:15:19 完成[第二次保存](engine_callee_live_20260927_1.json)。每個入口 `0x4acde0`、`0x349110`、`0x8ccfa0`、`0x8e1370` 讀 4 KiB，重讀一次；連同前後版本、原先 game.dll 指紋及兩個 EXE caller 指紋，實際讀取 **50,400 bytes**。四段重讀內容一致，檢查全部通過。保存 JSON SHA-256 為 `157ddf9f9f9c04265dbc80109441af7090fcf78316e8642781857668348f129a`。

[保存程式的控制流程分析](engine_callee_cfg_20260927.json)從四個已證實的直接呼叫入口出發，分別解出 106、29、188、170 個可達指令；保存範圍涵蓋其正常直接分支。分析不跟隨下游呼叫、間接分派或例外處理，因此不能把 4 KiB 當成完整函式邊界，也沒有證明這些函式在本次觀測時被呼叫。兩次使用者授權的擷取均已完成；保存資料的離線用途分析如下，交付核對記錄見[第二次擷取核對](ENGINE_CALLEE_VERIFICATION.zh-TW.md)。

### 第二次擷取後的用途判讀

[`+0x30` 下游分析](engine_30_callees_findings.zh-TW.md)確認 `0x4acde0` 將原先第一個整數參數取低 16 位，經未命名間接呼叫後寫入一個 16-byte 緩衝區的 `+2`；該緩衝區 `+0` 是 word `2`、`+4` 是另一呼叫的 32-bit 返回值。這符合 Microsoft [SOCKADDR_IN](https://learn.microsoft.com/en-us/windows/win32/api/ws2def/ns-ws2def-sockaddr_in) 的 family／port／address 布局，因此將其視為網路埠用途的推論。另一組 `2,2,0` 呼叫參數符合 UDP socket 建立形狀；間接目標未保存，不能據此給呼叫確切函式名稱。原先第二個整數（零設定分支為四）則原樣存到新物件 `+0xa8`；其更深層用途仍待核對。`0x349110` 只證明會把返回物件加入可增長的指標列，並無足夠證據把該列稱為玩家名單。

[`+0xf8` 物件建立分析](engine_f8_object_findings.zh-TW.md)將 `0x8ccfa0` 返回的外層物件連到其 `+0x18` 內部物件，並確認上層把同一個「設定加四」參數傳給 `0x8e1370`。在後者的保存程式中，堆疊配置的六個 32-bit 值是 **`N, N, 1, 1, 1, 0x0f`**；零設定分支的 `N` 為 `8`。它與官方 [PartyNetworkConfiguration](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/structs/partynetworkconfiguration) 的欄位順序逐項吻合：`maxUserCount`、`maxDeviceCount`、每裝置使用者數、每使用者裝置數、每裝置 endpoint 數，以及直接連線選項。

[請求及後續連線分析](engine_f8_request_findings.zh-TW.md)核對了該呼叫的參數形狀及另一份 invitation 配置，也吻合 [PartyManager::CreateNewNetwork](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partymanager/methods/partymanager_createnewnetwork)。同一保存範圍內的 `0x8e1970` 後續呼叫，亦逐項吻合連接網路、驗證本機使用者及建立 endpoint 的 SDK 參數。因此目前的高信心推論是：**這條零設定路徑提出網路使用者／裝置上限各八的建立請求**。尚未捕捉呼叫槽位的載入後函式指標，不能把此 SDK 對照寫成已證 export 綁定，也不知道為何設計成加四、該網路承載哪些流量，或本次遊戲是否執行此分支。官方說明該 API 只排入非同步建立作業；即使初始呼叫返回成功，仍需後續完成結果。因此此處的八不能當成八名玩家可同場任務的證據。

## 公開「8 人」線索的核對

本輪針對公開 GitHub 儲存庫與程式碼、Nexus Mods 及中英文搜尋結果尋找可重播的五至八位真人玩家同場案例，**沒有找到可驗證的《Helldivers 2》五至八人 Mod**，因此也沒有可核對的安裝檔、版本相容性或安裝步驟。這只是本輪搜尋的結果，不能證明私人專案不存在。官方[Arrowhead FAQ](https://arrowhead.zendesk.com/hc/en-us/articles/12571604061212-Helldivers-2-FAQ)與[Sony 公告](https://sonyinteractive.com/en/press-releases/2026/helldivers-2-joins-the-playstation-plus-game-catalog/)仍將合作小隊寫為最多四人。

[2024 年玩家自行擷取封包的原始貼文](https://www.reddit.com/r/Helldivers/comments/1cugtwc/technical_discovery_helldivers_2_can_on_paper/)稱 `FindLobbies` 回應含 `MaxPlayers: 8`，但作者同時寫明實際房間上限仍是四人，遊戲沒有使用八人的內容。這個服務欄位只能作為進一步研究線索，無法推翻本輪看到的四人加入判斷與四槽資料結構。

## 尚需跨過的門檻

| 門檻 | 目前證據 | 達標條件 |
|---|---|---|
| 房間建立與第五人入隊 | 官方僅支持四人；已見本機四人檢查。服務／平台是否另有限制未知。 | 第五名真人玩家可完成加入並被所有客戶端列入同一隊。 |
| 任務生成與同步 | 沒有五人玩法證據。 | 五名玩家在同一任務內能相互看見、行動，且目標、敵人、投射物與互動狀態一致。 |
| 任務生命週期 | 沒有五人玩法證據。 | 降落、增援、斷線重連、撤離、結算與進度一致，沒有第五人被遺漏。 |
| 八人擴展 | 沒有五人原型，也沒有八人負載測試。 | 五人門檻通過後再逐步增加至八人，核對所有欄位、介面與幀時間。 |

## 下一步驗證順序

1. **離線續查：** [儲存設計稿](PLAYER_COMPONENT_RELOCATION_PLAN.zh-TW.md)已補入property格式、元件容量、八項map、float consumer、q的confirmed-peer來源、子物件所有權／256格共用池、每筆11格的條件式模板預算，以及Wwise rank ID用途。接下來需收束其餘固定陣列存取、未接合caller／外部helper（包括新候選`72F780`／`730230`），確認pool重用／清理的一致性、其他用途峰值與模板等同性，再定義八槽配置、失敗處理、音效對應與釋放方案。房主、客戶端、roster、平台、tag `0x73`、loadout、tag `0xda` 與生成流程都需共同適配。參考player清單與實際載入內容的等同性、API payload／selector來源、事件 `0x4804fcf4/0x280728d6` 的hash→callback登錄仍未直接觀察。已有局部原生離線候選，但尚無充分資料可產生可安裝、可完成全鏈路的八人 Mod。
2. **核實引擎與平台介面：** 使用者已另行同意 [單一介面工具](tools/SPAWN_INTERFACE_PROBE.zh-TW.md)，於 12:49:36 完成一次 24,966-byte 擷取；指標及前綴重讀一致。[離線重播](spawn_interface_evidence.json) 與 [獨立核對](spawn_interface_independent_review.zh-TW.md) 已確認 `api+0xc0 → 物件首指標 → +0x18` 對應 `EXE+0x30ff50`。該轉接入口的九條指令呼叫範圍外的 `EXE+0x1ae380`，內部分配容量仍未取得。平台方面，第二次限定擷取已取得四個 EXE 入口的正常控制流程；仍需核對具名綁定、`+0xa8` 設定值的下游消費者、另一路平台房間的建立限制，以及非同步完成結果。PlayFab Party 的八使用者／八裝置配置推論不能替代這些驗證。三次各一次的限定擷取授權均已使用完畢，沒有持續讀取遊戲程序。 針對已定位的 `EXE+0x1ae380`，[固定單一下游工具](tools/SPAWN_CALLEE_PROBE.zh-TW.md)已完成 16 項離線測試與獨立審查，精確預算 24,868 bytes；已提出新的一次擷取授權問題，目前尚未執行。
3. **五人實測：** 需要五位可同時上線的玩家與各自帳號。先記錄官方四人基線及第五人的具體加入結果；任何候選變更都需在五台客戶端核對同一任務的生成、同步與結算。使用者目前無法安排五人，因此此項未執行。
4. **八人驗證：** 只有第五人完成全流程，且沒有未解的服務端或防作弊阻礙時，才投入六至八人擴展與穩定性驗證。遊戲更新後需重新核對版本與行為；[Arrowhead 支援文件](https://arrowhead.zendesk.com/hc/en-us/articles/20049276310300-I-have-Error-code-0x44415441)說明不相容 Mod 可阻止遊戲載入。

本輪沒有安裝、封裝或發布 Mod，也沒有對 GameGuard 或線上服務作繞過測試。
