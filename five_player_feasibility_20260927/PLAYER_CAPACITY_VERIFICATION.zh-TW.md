# 玩家元件、建立 guard 與索引下游：離線交付核對

本記錄涵蓋玩家元件、生命週期，以及後續的接收／分派／索引儲存離線研究。使用固定 build 25480438 的既有 code／readonly／unwind capture；這些續查沒有查詢或讀取活程序，也沒有修改、安裝或執行 Mod。

## `0.13.0` Registry 更新與關聯 ID reader 共用 B

[固定來源](roster_registry_update_native_findings.zh-TW.md)與[必要前提](roster_registry_update_native_prerequisites.zh-TW.md)收束完整 `B54E00`、其必要 `606520`，另固定 test-only `FD9BA0`。[候選](../eight_player_candidate_20260927/NATIVE_ROSTER_REGISTRY_UPDATE.zh-TW.md)將 root 六處與 helper 兩處 pointer／property／aux 基址改接共同八格 B；保留其他 tags、D 遍歷上界、entity flag 規則與兩個 helper 各自的 7FFF 語義。tag69、tag73 使用 roster 前才驗 binding/counts；tag69 匹配後另驗 map 容量、key 及有效且與 property ordinal 一致的 map 結果。共同產物為 **十五個 roster 函式＋不變 player_count 計畫**，59 個已知區域核對通過，嵌入的 v0.12 產物一致。

[8 組／87 次頂層測試](../eight_player_candidate_20260927/verification/native_roster_registry_update_tests.json)分為 **12 次原版完整基準**（root8、helper4）、**49 次候選完整返回**（root32、helper17）及 **26 次候選拒絕**（root20、helper6）。tag69 實際執行保存的 FD9BA0；tag73 實際進入原版或新606520。其他tags的資源calls由明示 ABI／順序／副作用替身提供。全部八格、dense-only／普通miss、aux狀態保留、bit旗標、其他tag、混合registry、拒絕恢復、地址與rel32邊界均有有界案例；沒有新增remove/getter串接執行。巢狀helper不重複加入頂層數。

目前累計 **144 組／4,272 次套件觀測**；總量保留舊版26次context prefix、原版基準、拒絕與預期原反例，並非4,272次候選成功。[Source審查](../eight_player_candidate_20260927/verification/native_roster_registry_update_review.zh-TW.md)及[oracle審查](../eight_player_candidate_20260927/verification/native_roster_registry_update_test_review.zh-TW.md)各自記錄範圍。原14個候選來源及13份報告保持原指紋，未重跑舊套件；新CLI建置逐byte等同保存的完整bundle。

這不提供引擎同步、有效context map／backing／resource、hook／unwind或nested reject handler。較早registry entries可在較晚拒絕前產生副作用；零容量／full-miss context map的原null缺口亦保留，不能視為任意輸入皆安全。下一有限離線切點是既有完整 `6054F0..605947` 的八格讀取與palette／玩家數通知，固定全部array／必要helper後收束；本輪不啟動該追查。平台加入、角色建立與五至八帳號任務全流程仍未驗證。

## 歷史：`0.12.0` 移除前處理與共同八格候選

[完整 `605950` 來源與六處陣列位點](roster_departure_native_findings.zh-TW.md)固定 1,503 bytes／346 條指令，另有必要 network reader `606820`。[離線原生候選](../eight_player_candidate_20260927/NATIVE_ROSTER_DEPARTURE.zh-TW.md)把 pointer、primary、property 六次直接讀取接至共同八格 B，並僅在 `6059EE` 改呼既有八格 getter。入口驗 S/B、entity、map／ordinal、`P≤D≤T≤8`，拒絕於首次外部回呼與非 stack 副作用前；原三個 primary helper、關聯物件支線、manager 迴圈及尾跳保持。兩個原 `D−1` 通知改用**新增候選政策** `D−(ordinal<D)`，使有效 pending 移除不扣 dense count；尾部 `player_count` 保留原移除前當時 D。共同建置含 **十三個 roster 函式**及上一版 `94C9C0`／`94BE10` 玩家數 patch 計畫，尚無安裝器。[必要 count/state 契約](roster_departure_candidate_contract.zh-TW.md)要求 S、B、target、map／ordinal 與分段在整段回呼及後續真正移除前穩定，入口 guard 不能單獨證明。

[7 組 departure 測試](../eight_player_candidate_20260927/verification/native_roster_departure_tests.json)記錄 **43 次頂層 x64 執行**：7 原四格完整基準、16 候選完整 departure、17 候選入口拒絕、1 remove 串接及 2 getter 串接。實際保存指令涵蓋三個 primary registration helper、`FD9C80`／`FD9D40` 有效路徑與 map-delete；外部 controller、資源建立、manager queue、`94C9C0`、`60C2A0` 與 tail 是逐個核參數／順序的替身。[獨立 oracle 審查](../eight_player_candidate_20260927/verification/native_roster_departure_test_review.zh-TW.md)未見此有限範圍的阻塞缺陷。截至該v0.12階段累計 **136 組／4,185 次套件觀測**，其中仍有舊版 **26 次只跑 `94C9C0` prefix**、原版基準、拒絕與預期原反例；4,185 不是候選成功次數，也不是完整遊戲或多人執行。

這份候選沒有證明回呼不重入、外部資源可用、真實 pending caller 可達、`94C9C0` 十五個 callsite 端到端執行或完整名冊生命週期。候選避免把 pending D=0 的參數算為 `FFFFFFFFh`，但 v0.11 UI consumer 對 0 仍夾至 1，`60C2A0` 對 5–8 僅有已知數值路徑。該輪B54E00切點已由上述v0.13接入；P1 平台加入、P2 角色建立、同步、unwind、hook 與五至八帳號同任務驗收仍缺。

## 歷史：`0.11.0` 玩家數原生 patchplan 與當時驗證總量

[完整 `94BE10` 指令證據與切點](roster_player_count_native_findings.zh-TW.md)、[必要前提](roster_player_count_native_prerequisites.zh-TW.md)固定四段 chained body 1594 bytes／359 指令、直接 tag predicate，以及 `94C9C0` 十五個 count 傳參點。[新候選](../eight_player_candidate_20260927/NATIVE_PLAYER_COUNT.zh-TW.md)以 `94CA30` 5-byte 原位 patch 把 unsigned clamp 上界 4 改 8，另在 `94C07B` 6-byte 切點跳往 51-byte trampoline；僅對 **max=4 且 min≤4** 的來源 record 把比較上界視為 8。其餘 min/max、raw0→1、override 與 tech-level 索引保持原語義。這是使 5..8 在有效 `1≤min≤max≤4` profile 上沿用原 count4 選集的新增政策；真實遊戲資產的有效 profile 尚未取得。[原生 source](../eight_player_candidate_20260927/Native/player_count.py)只生成離線 bytes 與 patch 計畫，沒有安裝程序。

[7 組保存測試](../eight_player_candidate_20260927/verification/native_player_count_tests.json)通過 188 次 x64 模擬觀測，須拆成 **162 次完整 `94BE10` filter**（65 原版／97 候選）和 **26 次只到 `94CA3A` 的 `94C9C0` prefix**。有效四人 profile 的 1..4 原／候選、候選 5..8 對原4，均核完整輸出 bytes／非 stack page；另核 min5/max4 空範圍、override、tech 1/3/10、真實 `177E3C0` predicate 及四個明示 helper stub。[獨立 oracle 審查](../eight_player_candidate_20260927/verification/native_player_count_test_review.zh-TW.md)未見局部阻塞缺陷。截至該 `0.11.0` 階段總計 **129 組／4,142 次套件觀測**，內含原版基準、26 次 prefix、既有預期原反例與候選執行；4,142 不能稱為候選成功次數，prefix 亦非完整 context 執行。

在該 `0.11.0` 階段，真實 R8/R9 record min/max、`94C9C0` 十五個 callsite 的端到端資源選擇、`605950/606820` 與共同 B 整合、pending D=0 導致的 `FFFFFFFFh` 與 count/state 生命週期都未閉合。安裝、同步、unwind、外部服務、第五人及八帳號同任務均未驗證；當時的下一個有限切點是 P3 移除前讀者改接。

## 歷史：`0.10.0` 移除前計數調查（當時未新增候選版本）

[來源與結果](roster_departure_native_findings.zh-TW.md)、[前提](roster_departure_native_prerequisites.zh-TW.md)及[原指令 probe v2](roster_departure_native_probe_v2.py)限定原四格三個狀態，依序執行保存的清理與移除程式。兩個通知均收到 D−1；dense T1/D1 移除後 D0 相符，pending T2/D1 移除後 D1 則不符，pending T1/D0 的通知參數為 FFFFFFFF、移除後 D0。v2 使用真實 `FD9C80` 的 7FFF→null 分支，取代早期強制 null 替身；四個通知仍採不修改名單的明示契約。外層派送為合成呼叫，因此不宣稱真實 caller 可達 pending 或完整回呼副作用已驗證。

有限下游指令另確認 `94C9C0` clamp 1..4、`60C2A0` 四種命名資源加數值 fallback；這不是平台容量或八人可行性的實測結果。此調查用於否定「只改六個陣列讀取即可完成 departure」的方案；截至該 0.10 階段，候選版本、122 組及 3,954 次既有套件執行總數不變。

## 歷史：`0.10.0` 換位後的 network-index getter

[完整 getter 來源](roster_getter_native_findings.zh-TW.md)、[前提](roster_getter_native_prerequisites.zh-TW.md)與 evidence／recheck 固定單一 165-byte／43 指令 body。[候選](../eight_player_candidate_20260927/NATIVE_ROSTER_GETTER.zh-TW.md)輸出 354 bytes，兩階段 guard 加唯一 property 改接，保留原普通 missing 與 full DWORD；十二函式共同建置有 47 個有限已知區域。

[7 組／84 次測試](../eight_player_candidate_20260927/verification/native_roster_getter_tests.json)通過 73 候選／串接、10 原基準／missing，另預期重現 1 次原 empty-key 假命中；不把後者列為正常相容性案例。分類 fixture 使用固定 hash，移除則實際執行 map-delete／mover；ID 67 換位後讀回 FEDCBA98，被刪 ID 19 回 FFFFFFFF 且不讀 property。[Source 審查](../eight_player_candidate_20260927/verification/native_roster_getter_review.zh-TW.md)及[oracle 審查](../eight_player_candidate_20260927/verification/native_roster_getter_test_review.zh-TW.md)均完成。

截至該 0.10 階段，原十一個候選來源、十套報告未改且未重跑；分類 fixture 也保持固定指紋。當時累計 122 組／3,954 次執行，其中移除反例 2 次、getter 原假命中 1 次；仍無遊戲／多人驗收。

## `0.9.0` 分類切換及共同八格儲存

[分類來源](roster_classify_native_findings.zh-TW.md)與[必要前提](roster_classify_native_prerequisites.zh-TW.md)固定兩完整 body 及三個暫存 helper，evidence／recheck 逐 byte 相同。[候選](../eight_player_candidate_20260927/NATIVE_ROSTER_CLASSIFY.zh-TW.md)改接 37／51 個 array operands，保留分支／helper／global 的完整重定位；移入／移出輸出分別 1,921／2,275 bytes，十一函式 bundle 共 44 個有限已知範圍。

[新增指令測試](../eight_player_candidate_20260927/verification/native_roster_classify_tests.json)用獨立 bytes／map／count oracle，保留 enter primary 不對稱語義；暫存使用 create／allocate／release／release 契約 stub，檢查 scope、size／alignment、Windows shadow space、volatile clobber 與 buffer 生存期。原四格基準與候選直接配對返回 RAX；連續分類後 receiver 寫入 ID 67 的新 ordinal 3，network index 保持 7。完整外層 caller／配置失敗恢復／同步尚未實測。

[Source 審查](../eight_player_candidate_20260927/verification/native_roster_classify_review.zh-TW.md)完成全部 429 條原指令與 88 位點核對；原十個來源和九套報告指紋維持，這輪沒有重跑舊測試。[最終 oracle 審查](../eight_player_candidate_20260927/verification/native_roster_classify_test_review.zh-TW.md)核 7 組／853 次（783 候選／串接、70 原四格基準），660 次涵蓋全部合法分段。十套保存結果累計 115 組／3,870 次，含先前 2 次預期原反例；不把總數當候選成功數。

## `0.8.0` 完整分段移除與重新加入

[移除完整來源](roster_remove_native_findings.zh-TW.md)固定兩個 body 及真正 map deletion helper，共 83＋78 條原指令，evidence／recheck 逐 byte 一致。[獨立前提審查](roster_remove_native_prerequisites.zh-TW.md)確認 missing ID 回 0、prefix bit 契約與原 dense／pending 資料遺失邊界。

[新候選](../eight_player_candidate_20260927/NATIVE_ROSTER_REMOVE.zh-TW.md)在刪除前做有界讀查，將 pointer load 與 mover 改接共同八格儲存，dense 完成後若 Dnew<Tnew 補上 Tnew→Dnew 搬移；包含 Dnew=0。Legacy／registered 分別 717／705 bytes。這項補位是新增語義，不宣稱原碼已有；外部 alias／資源／caller／同步仍須整合。

[9 組測試](../eight_player_candidate_20260927/verification/native_roster_remove_tests.json)通過 2,293 次 x64 執行：2,141 候選／串接、150 原四格基準、2 預期原反例。完整分段共 1,980 次核 survivor IDs、四陣列、counts、map 雙射及碰撞查找；另含拒絕、ASLR、rel32、共同建置與連續追加／移除／重加／接收。[Source 審查](../eight_player_candidate_20260927/verification/native_roster_remove_review.zh-TW.md)未見局部缺陷；[oracle 審查](../eight_player_candidate_20260927/verification/native_roster_remove_test_review.zh-TW.md)指出的 registered RAX 配對與非零新 ordinal 接收已補強，最後套件重跑通過。

九套保存結果累計 108 組、3,017 次模擬執行，其中兩次是預期原反例；不能把總數都當成候選成功。舊九個候選 source／八套結果保持原指紋，沒有重跑舊套件。沒有遊戲／帳號／任務執行。

## 原四格整理反例：未產生 compactor

[完整 `60CC70` 證據](roster_compact_native_findings.zh-TW.md)與[獨立前提審查](roster_compact_native_prerequisites.zh-TW.md)確認 inline P→D 後的 shared mover 是 D→P，沒有保存原 D。518-byte／100 指令的 evidence/recheck 逐 byte 一致；已知 caller 的有限檢查未提供 roster count guard，仍未閉合所有 alias／上游狀態。

[原四格執行反例](roster_compact_counterexample.zh-TW.md)在 Unicorn 執行固定原 bodies 與真實 helper，35 個 `P≤D≤T≤4` 組合中，10 個 `P<D<T` 失去實體／唯一性／map 一致性，其餘 25 個保留。最小例 `P=0,D=1,T=2` 由 `[A,B]` 變成 `[A,A]`。另執行原 dense→append→compact 三步合成序列，合計 38 次 top-level 呼叫；此序列在遊戲內的可達性未證。這是被否定方案的調查，不加入下述候選通過數。候選原始碼保持 0.7，下一步先查 pending／prefix caller 契約。

前述反例的後续[派送查核](roster_append_dispatch_findings.zh-TW.md)另以固定來源重播及獨立重跑得到逐 byte 相同的 JSON。它確認第一張表的註冊、第二張表的已知 reader 及整理更新鏈；沒有閉合第一張表 reader 或兩者的完整順序。這項保存程式核對也不加入候選執行通過數。

## `0.7.0` 四插入與持續記錄串接

[插入來源](roster_insert_native_findings.zh-TW.md)固定四完整 body 共 187 指令，以及 map helper 的 110 bytes／34 指令；evidence/recheck逐byte一致。獨立 source 審查核56個array operands、16個原分支／call、4個RIP、4個capacity比較與其餘107條原bytes。入口guard、R11改接、near branch relocation與七函式交疊檢查未見具體局部缺陷。

[9 組新增測試](../eight_player_candidate_20260927/verification/native_roster_insert_tests.json)通過515次x64執行，核有效分段／旗標、原四格、整頁bytes／counts、拒絕、兩種append在同一名冊八次追加後拒第九次，以及插入→producer→receiver。另一代理核oracle並指出receiver呼叫計數沿用前段累計，已清零並加斷言、重跑確認；見[審查紀錄](../eight_player_candidate_20260927/verification/native_roster_insert_review.zh-TW.md)。沒有真實serializer／transport／帳號參與。

八套保存結果累計99組／724次模擬執行，這輪只跑新增套件。原八個候選source未修改。Dense D==T為候選新增限制，map/newkey/synchronization仍需外部前提；caller／pending-tail、壓實／分類／移除／讀者、初始化／發布／清理、unwind／hook及八人驗收尚未完成。

## `0.6.0` 四陣列搬移與三函式串接

[完整 mover 證據](roster_move_native_findings.zh-TW.md)固定原 430 bytes／78 指令、三個 fragments、26 個位移與兩個切點；evidence 與 recheck 逐 byte 相同。独立靜態審查核原 capture、四陣列基址、首次写入前的 guard、map 前恢復 S、相等 ordinal 返回與拒絕 ABI，未發現局部缺陷。

[11 組新增測試](../eight_player_candidate_20260927/verification/native_roster_move_tests.json)通過 103 次 x64 模擬執行，包括完整八格 64 組、原四格 16 組、地址／ordinal邊界與 producer→move→receiver 串接。Whole-page oracle 核四組 bytes、原來源與 counts 保留、map 更新和接收端重新尋址；原函式沒有在不存在的八格 inline 布局上作對照。首輪 SSE write hook 粒度斷言已修正；[審查紀錄](../eight_player_candidate_20260927/verification/native_roster_move_review.zh-TW.md)保留原因、修正及獨立 bundle／chain 核對範圍。

七套保存結果合計 90 組／209 次模擬執行；這輪只重跑新增套件，其餘來源指紋保留。共同範例可純 bytes 重產，沒有原生主機或遊戲執行。完整 `680h` 儲存初始化、各插入／壓實／分類／移除與其他讀者、unwind／reject／hook、同步及多人驗收仍未完成。原 map 失敗行為仍是必要前提，且[全零不等於原生初始化](roster_move_native_prerequisites.zh-TW.md)。

## `0.5.0` 產生端與共同建置

新增 [producer 完整來源](roster_property_producer_native_findings.zh-TW.md)固定 `60C640..60C882` 的 578 bytes／130 指令；主代理另核原 capture、正常 CFG、C6C9 對 allocator／八 stores 的必經關係與 wrapper caller，見[來源核對](roster_property_producer_native_review_checks.json)。[原生候選](../eight_player_candidate_20260927/NATIVE_PROPERTY_PAIR.zh-TW.md)保留配置／descriptor 行為，將八個 property writes 導向 receiver 共用的八格儲存。

獨立於 emitter 作者的 [10 組測試](../eight_player_candidate_20260927/verification/native_roster_producer_tests.json)通過 54 次 x64 執行，涵蓋原碼對照、實際 index leaf、allocator volatile clobber、四個 relocation、拒絕前無配置及 producer→receiver 資料橋。另 [4 組 pair 測試](../eight_player_candidate_20260927/verification/native_roster_pair_tests.json)通過共用 S/B 與有限交疊檢查。0.5 階段合計 79 組測試；106 次模擬執行屬 receiver／producer 內部案例，不另外加總。Allocator 採成功契約、bridge 沒有跑 serializer／transport，所有遊戲與多人驗收仍未通過。

[有限 consumer 清單](roster_property_consumers_native_findings.zh-TW.md)將下一個實作定位為 `60C410` 搬移。該函式先改其他三個平行陣列，再 copy property、修 map；不能在 property 切點才檢查失敗，也不能永久偏置仍供 map 使用的 S。全域 alias 與 sidecar 生命週期仍未閉合。

## `0.4.0` 原生 receiver 候選的指令執行驗證

候選 `0.4.0-offline` 新增 [375-byte x64 receiver 產生器](../eight_player_candidate_20260927/NATIVE_RECEIVER.zh-TW.md)。固定原 303 bytes／72 條指令的來源指紋，保留原 lookup、八個 DWORD 的讀寫與 cursor 順序，將符合 roster 綁定的 ordinal 0..7 導向八份獨立儲存。

[獨立測試報告](../eight_player_candidate_20260927/verification/native_roster_receiver_tests.json)記錄 11 組測試、52 次隔離 x64 模擬執行，零 failures／errors；另一代理完成原指令與產生碼的靜態審查。主代理核對程式、解碼、報告及指紋，詳見[審查範圍](../eight_player_candidate_20260927/verification/native_roster_receiver_review.zh-TW.md)。三套既有 Lua 測試的 54 組仍由相同來源指紋支持；四套共 65 組，52 次模擬是原生測試內的執行次數，不另計測試組數。

已驗證合成資料的寫入、原 network index 保留、cursor、hash collision／miss、拒絕前不寫 payload 目的地、正常 register／stack 恢復及 RIP／rel32 邊界。拒絕時仍需外層處理原 frame 並終止完整 dispatch；binding 檢查在 map lookup 後，不能保護無效 map 指標。其他 producer／move／reader、儲存生命週期、同步、Windows unwind、hook 與遊戲執行仍未完成，`installable=false`。

P5 的[第二 S 來源有限收束](indexed_float_double_secondary_findings.zh-TW.md)及[整合邊界](native_integration_boundary.zh-TW.md)保留明確缺口：所有 20 個第二 S 仍須按實際配置保留；正常 call 順序不證明引擎互斥。沒有新的可接合來源時停止擴搜，離線實作接續 P3 的其他 roster 存取。

## 候選清單及剩餘池使用者的收束

新增 [owner layout 候選](../eight_player_candidate_20260927/OWNER_LAYOUT.zh-TW.md)把直接 constructor／cleanup 清單轉成 305／325 個已知地址，並要求 packet 完整列出、不含搬移後舊玩家副本，也不讓額外 S 覆蓋目前整段玩家 records。獨立審查找到的 record 頭尾非 S 區域漏檢已重現及修正；[23 組測試](../eight_player_candidate_20260927/verification/pool_owner_layout_tests.json)通過，修後審查已接受。原 preflight 11 組及 snapshot 20 組的來源指紋未變，三套合計 54 組離線測試；[審查紀錄](../eight_player_candidate_20260927/verification/pool_owner_layout_review.zh-TW.md)保留實際範圍。

三條研究的正式證據均與各自同來源重跑逐 byte 相同：

| 支線 | 交付與限制 |
|---|---|
| [七個單例](indexed_float_pool_singletons_findings.zh-TW.md) | v3 證據 `379977cc2a1f193646d9ae8ab7143694c3db20676f133b7c762e6860eb2f1d41`。主代理核 final v3 原始 rows／來源／算式；獨立代理審查 v1/v2 並提出的 register／stack 條件已納入 v3。固定模板子集合條件式至多 12 格，非全池或舊狀態上界。 |
| [20 筆雙 S](indexed_float_pool_double_records_findings.zh-TW.md) | v2 證據 `324b4d436d28b041963d5cb27db0a3496350c292a0e9b026bc885dc3bfc34650`。上游有條件至多 20 個輸出、caller 仍要求初始 count0；全 40 個 S 不依 active count 裁剪。獨立代理已核完整 roots、原始 rows、reaching 與 guard；第二 S 的完整配置來源仍缺。 |
| [模板 ID0](indexed_float_template_zero_findings.zh-TW.md) | 正式證據 `d44d5741d7fc0f8b5122f8285c466442f897328c5233348853f8bce53f37125d`。66 個 selector 的非零分類及 C2E0 分支獲獨立核對；最後修正 update／constructor 標籤並重跑。ID0 是否實際為空仍需 supplied bytes，不自動填 count0；事件／資源恢復與原生執行未完成。 |

這些結果推進八人儲存、資源生命週期與失敗處理所需的候選程式；尚未完成一致資料來源、引擎同步、全域 aliases／共存峰值、原生 executor 或多人驗收。平台加入及第五人角色建立仍是整體可行性的優先缺口。

## 最新續查：q、資源池與 Wwise ID

本次另唯讀檢查本機build25480438所選boot的hash_lookup資產及94個loose patch metadata；這是磁碟檔案操作，沒有擷取遊戲程序。代理在交叉審查階段因用量限制停止，主代理接手核對已保存成果，詳見[審查範圍](indexed_float_remaining_review.zh-TW.md)。

| 支線 | 成果與驗證 |
|---|---|
| [外部q來源](indexed_float_external_index_findings.zh-TW.md) | 確認host peer key→confirmed-peer record→32-bit network index。重播逐byte一致；主代理核3,296個不同指令位置、12完整roots，另獨立重建12個正常CFG、14個暫存器定義查詢與2個必要分支。 |
| [子物件與共用池](indexed_float_subobjects_findings.zh-TW.md) | 確認fresh initialization、active資源唯一所有權、256格共享池及partial配置／同ID不重試。重播逐byte一致；核13完整roots、2個direct-call leaves與1,186個不同位置，另逐讀關鍵生命週期。 |
| [Rank音效ID](indexed_float_rank_ids_findings.zh-TW.md) | 確認Wwise事件／浮點API、hash_lookup載入及missing→0。重播逐byte一致；核9完整roots、1,924個不同位置。所選磁碟表六個event key存在、兩個parameter key缺失，沒有推論runtime一定使用該表。 |
| [兩個helper本體](indexed_float_helper_boundaries_findings.zh-TW.md) | 在保留D及其他欄位的前提下，`142FA60/1432F10`本體無直接本批record／metadata陣列基址要改。主代理核4完整roots、440個不同位置；另一代理語義審查未完成，兩個未接合候選仍不列為同D已證路徑。 |

```text
indexed_float_external_index_evidence.json
c83db6d2e7c5033b3127d95227f29d24e11605415b55616d9854c2245ed4bf5d

indexed_float_subobjects_evidence.json
5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54

indexed_float_rank_ids_evidence.json
dfefbca1b590691cf498748d39554a2a020f93e5c8e7bbc6ded6a551df117461

indexed_float_helper_boundaries_evidence.json
c70e0f48ce069decf271f9b69631695da41faaa7c5a373263d0f57a315e6e5d6

indexed_float_rank_asset_manifest.json
2f172470d8c13495536e3844b8a51b46821e5f393185cd51f2f363721a03ef01

indexed_float_wwise_hash_lookup_current.bin
3b34c46a17f0aa1003a30cf23a6010c5f08fddcfc5ab9a9020ffd2ef06091557
```

這些是限定來源與必要設計條件的驗證，並非可安裝補丁、全部consumer清單或八人玩法驗證。尚需pool初始化／其他用途峰值／template等同性、其他caller／alias、音效對應與執行期／多人實測。

### 指定模板節點預算續查

[模板預算證據](indexed_float_template_budget_findings.zh-TW.md)包含完整initializer root（6,440條指令）、五個完整leaf（192條）及四段直線emission blocks。得出每筆11格、新增四筆44格、八筆88格的條件式預算。33個Python合成案例共5,051步，覆蓋兩處conditional branches的真假方向；沒有native執行。

主代理另以不同核對程式檢查6,788條rows／6,654個不同地址的原bytes、完整initializer fragment及call counts。同來源重跑輸出逐byte一致，正式JSON SHA-256為`575501706ca9dd257f4cd155325b6a809ed303037736359fb4da6918ee5117bc`；見[核對記錄](indexed_float_template_budget_review_checks.json)。這次沒有獨立代理語義審查。第四次capture輸出仍不存在，沒有讀取活程序。

初始化探索另找到`72F780`／`730230`兩個reader候選，caller的RCX身分尚未閉合；不計入已證同一D或已完成改接的consumer。

### 共用池的初始清零來源

[初始零值證據](indexed_float_pool_initial_zero_findings.zh-TW.md)接上外層`7AF7628`-byte clear與同一owner／manager／D的位址鏈。重播核6個完整roots、14個unwind fragments、5,601條完整-root指令，加startup prefix；22項register reaching-definition及clear必經才發布的CFG檢查通過。它只證明初始zero-fill來源，不證明後續constructor入口仍為零或active池可reset。

主代理另核5,667條rows／5,638個不同地址的原bytes、完整fragments與位址算式；[額外核對](indexed_float_pool_initial_zero_review_checks.json)及同來源重跑逐byte一致。正式JSON SHA-256為`bde73bc5efde3267f812c7c2077264fd91ecec261a6054fa23b63c87b0c874e1`。未執行native code、未讀取活程序，亦無獨立代理語義審查。

### 共用池的直接子物件生命週期

[生命週期清單重播](indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)核對2個完整roots、381條指令，原305個S建立／清理位址與順序完全相同。三個位址投影情境均以零／CC初始bytes重播：原四筆305項無衝突；原基底改八筆325項有27組S區間重疊；八筆獨立儲存325項無重疊。引擎callee採有限contract，不是native資源操作。

主代理另核388條rows／381個不同地址的原bytes及全部S區間兩兩比較，見[核對記錄](indexed_float_pool_lifecycle_inventory_review_checks.json)。重跑JSON逐byte一致；SHA-256為`7722b443b293e565b1600fccbbb8820c0ef01e281f86aac237abb1419e20fda6`。唯一所有權、有效indices、正確占用計數、context生命週期、沒有重入修改仍是回收推論的前提；沒有獨立代理審查或多人實測。

### 可選成員與四組其他模板

[可選成員重播](indexed_float_pool_optional_members_findings.zh-TW.md)包含`142F530/142F780`兩個完整roots、四個unwind fragments、141條指令，10項argument reaching-definition與兩個可選配置call的必要edge檢查。四個新template blocks各以零／A5合成payload重播，主模板`20/21/2F/22`均一格；假設條件與未觀察的保留配置另列，不將72格子集合預算當作整池峰值。

主代理另核248條rows／217個不同地址的原bytes、四個template immediate、八個旗標literal及四個counter欄位。見[核對記錄](indexed_float_pool_optional_members_review_checks.json)；同來源重跑逐byte一致，SHA-256為`2f955ad49c85cf0b1e24379c2fb3d8b75e15da6b6957ddda29b250af2429f436`。沒有獨立代理、native或多人驗證。

本次交付前檢查通過六個正式證據／資產指紋、五支Python程式語法解析、三份獨立重播輸出逐byte一致，以及九份相關Markdown的157個本機連結。第四次擷取輸出仍不存在；沒有新增live程序操作。

### 四組counter上限與快取清零

[Counter重播](indexed_float_pool_counter_bounds_findings.zh-TW.md)核三個完整roots、16個unwind fragments、2,186條指令；五條guarded append涵蓋兩條五筆分支，76個accepted count情境與315項reaching-definition核對。有限掃描九個直接writer分為四個清零與五個increment；有效初值等條件下維持1／64／5／1上限。266處無call後段D寫入都不碰305個S與pool區，不能把count／cache清零當作節點釋放。

主代理另核2,540條rows／2,190個地址的原bytes、五個JAE opcode／容量literal及306個保護區間的零重疊，見[核對記錄](indexed_float_pool_counter_bounds_review_checks.json)。重跑逐byte一致，正式SHA-256為`aae3906ab3672a3b0f8ed631fdfddeec11bb7b636e3b5bfbb7083d3554f048d4`。三個既有代理因用量限制為errored，沒有獨立代理、native或多人驗證；computed aliases、其他旗標writer與完整回收仍未閉合。

### 32筆三S模板與轉換餘量

最新另補[32筆三S與模板轉換v3](indexed_float_pool_triple_members_findings.zh-TW.md)：重核三個完整roots共8,299條指令、四個新payload helper leaves共42條指令，29項reaching checks、33個起始count條件歸納、12模板各兩組payload重播。四個容量5／6的轉換模型呈現最後需求5但峰值6，以及partial後同ID不重試；全域可達性與opaque callee不干擾均未證。主代理另核436條rows／359個地址、各root SHA／指令數、emitter計數與轉換算式，見[v3核對](indexed_float_pool_triple_members_review_checks_v3.json)。重跑逐byte一致，正式SHA-256為`7a5b7ef002c671d698edd6c663b791a7306eda2b09a238b5d8f187393c04bd60`。沒有獨立代理或執行期驗證。

## 前一輪：動態容量、八項 map 語義與索引暫存

| 支線 | 正式證據與獨立核對 |
|---|---|
| 元件 3 | [evidence](component3_capacity_evidence.json)：11 roots、797 條指令；另一代理獨立重播逐 byte 相同，另重核完整 fragments 與原 bytes，確認資料512／map1024、雙陣列增加256、map獨立增長與搬移，見[審查](component3_capacity_review.zh-TW.md)。 |
| 元件 260 | [evidence](component260_capacity_evidence.json)：16 roots、1,959 條 root 指令、50 條 leaf 指令及47 pins；主代理核2,164筆記錄／2,123個不同位置、完整 fragments及backing算式，見[審查](component260_capacity_review.zh-TW.md)。已補上property末段身分。 |
| 八項共用 map | [正式 evidence v4](component_map_capacity_evidence_v4.json)：65,536種home分布、80,640種完整刪除順序、4,506次模型／指令對照。主代理獨立重跑逐byte相同，另核三roots共184條原指令；112條helper指令及11個conditional兩結果全覆蓋，見[審查](component_map_capacity_review.zh-TW.md)。 |
| 雙 float 的有限 consumers | [正式 evidence v2](indexed_float_consumers_evidence.json)：5,231個instruction rows，涵蓋12 roots的5,126條正常指令、額外視窗與2個caller保存／還原pins。另一代理重產逐byte相同並核全部原bytes、邊界、asm；另独立建立5,507條指令的完整caller CFG及7個reaching-definition查詢，見[審查](indexed_float_consumers_review.zh-TW.md)。確認metadata／stack容量、2×2遍歷及缺local時八個rank條件。 |

```text
component3_capacity_evidence.json
1ed27a70a2a1662c3e324c774da877687ae0388d54fe4320e94057f07fd14330

component260_capacity_evidence.json
567cc06bda9590295bef91b61e20b6f5cb04c8c4410289e39f2c67a76fd09455

component_map_capacity_evidence_v4.json
f8918247d729a1bde957739ffa7d724ffceba831416e8d526aacc5f70e53e61b

indexed_float_consumers_evidence.json
503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578

indexed_float_consumers_review_caller_cfg.json
b1ac8e336b754ee5ec7cc55128ddb3b5670eaf11f9419c38843a5b472cd5ef90
```

容量模型及指令直譯只在 Python 人造狀態上運行，沒有執行遊戲碼；部分 map／lookup sentinel 的相等是測試假設，非執行期觀測。結論支持保留元件3／260既有動態儲存，並在最多八個有效key等前提下保留八buckets，沒有驗證八人聯機。

雙 float consumer 的數字包含重複引用，亦與前置證據重疊，不代表全遊戲覆蓋率。`142CB90` 的51-byte尾段另保存為3-byte NOP及實際被分派指令引用的12個DWORD RVA，沒有當成指令計入；完整caller CFG是[獨立補證](indexed_float_consumers_review_caller_cfg.json)，主replay核其指紋及新增pins，不宣稱自行重算該完整CFG。有限清單仍有外部索引q、generic helpers及ID資源語義等未閉合邊界。

交付前檢查另通過四份正式證據及caller補證的五個SHA-256、四支replay語法解析、三份獨立重播輸出逐byte一致（元件3、共用map、float consumers），以及13份Markdown的143個本機連結。元件260採上述原始bytes／fragments及算式的獨立核對。第四次擷取輸出仍不存在；交付檢查沒有查詢活程序。

## 接收、分派及剩餘 consumer

| 支線 | 正式證據與独立核對 |
|---|---|
| Roster property receiver | [evidence](roster_property_receive_evidence.json)：完整 303 bytes、72 指令、4 fragments；另一代理獨立核對全部 bytes、42 pins 與正常 CFG，確認 index 原樣 32-bit copy 及有效 ID／buffer 前提，見[審查](roster_property_receive_review.zh-TW.md)。 |
| 選定 property dispatcher | [evidence](property_dispatch_evidence.json)：11 roots、754 條 root 指令、94 span 指令與 38 pins；主代理核 915 筆記錄／848 個不同位置、全部 fragments 及 1,855 個 table entries，確認 selector `3A7` 分支共 280 bytes，見[審查](property_dispatch_review.zh-TW.md)。 |
| Network-index 雙 float 區域 | [evidence](indexed_float_storage_evidence.json)：814 條保存指令／pins；主代理核 832 筆遞迴記錄／812 個不同位置、六個完整 root、七組 base prefix，確認同一 D 與 index 4／7 相鄰衝突，見[審查](indexed_float_storage_review.zh-TW.md)。 |
| 元件 43 內嵌更新 | [evidence](component43_inline_consumer_evidence.json)：四 fragments、2,821 bytes、687 指令；另一代理重建正常 CFG、85 節點區段及 RDI 賦值支配關係，排除 roster／stack 的相同 displacement，見[審查](component43_inline_consumer_review.zh-TW.md)。 |

```text
roster_property_receive_evidence.json
bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10

property_dispatch_evidence.json
9cabca2fa61fd59e9c776230da80ad68716f947c46f56c6b9c203ba011d0d55d

indexed_float_storage_evidence.json
11e984e270540eded0e141f821ddfbb22118c0b99645237eca15e14149d42378

component43_inline_consumer_evidence.json
f8a4a4e5ca22f490cc80614019fd683f5b532a71e8597dfb6686751c5ba069a3
```

不同計數包含額外 pins 與重複引用，不能直接相加當成覆蓋率。此次新結論已整合進[總報告](REPORT.zh-TW.md)與[設計約束](PLAYER_COMPONENT_RELOCATION_PLAN.zh-TW.md)。這些驗證固定離線來源及推導，不證明 player 當前採用 selector `3A7`、第五人觸發 writer，或八人已能遊玩。

## 後續：五個新增元件的生命週期與布局

目前設計彙整為[八槽儲存設計約束](PLAYER_COMPONENT_RELOCATION_PLAN.zh-TW.md)。後續正式證據及交叉審查如下；原先四條支線保留於下節。

| 正式證據 | 來源核對與獨立審查 |
|---|---|
| [component33_250_lifecycle_evidence_v2.json](component33_250_lifecycle_evidence_v2.json) | 1,883 條選定 code-body 指令核回原 capture；獨立重播逐 byte 一致，另核 37 個 semantic pins。審查修正 250 的 `+160` 第二組 byte 資料、分類增加清零／分類減少交換，見[審查記錄](component33_250_lifecycle_review.zh-TW.md)。 |
| [component41_lifecycle_evidence_v2.json](component41_lifecycle_evidence_v2.json) | Replay 保存 14 roots／1,260 指令、3 leaves／112 指令、305 pins。主代理另核遞迴資料中的 1,982 筆記錄、1,702 個不同位置、全部 root fragments 及邊界算式，見[審查記錄](component41_lifecycle_review.zh-TW.md)。 |
| [component43_lifecycle_evidence.json](component43_lifecycle_evidence.json) | 11 roots 共 550 函式指令，連同 owner 片段為 614 個不同位置；另一代理重建全部 fragments、核對原 bytes、單向壓實及 owner 來源，見[審查記錄](component43_lifecycle_review.zh-TW.md)。 |
| [component238_lifecycle_evidence_v2.json](component238_lifecycle_evidence_v2.json) | 1,652 unwind 指令、212 proven-leaf 指令及 82 pins；獨立審查補上 owner tick 的暫存器恢復證據，再核 v2，見[審查記錄](component238_lifecycle_review.zh-TW.md)。 |

```text
component33_250_lifecycle_evidence_v2.json
dfb125ab3edd6b9672eb725981beecb91e1768da9d44b92522e28fd971155280

component41_lifecycle_evidence_v2.json
0f902df704cffb16992d483e099867f5e05708e6d32bdf1672128eca744721df

component43_lifecycle_evidence.json
e0e3f9fcfec8359eb3f777a7537a2c53d8635cc1c754d1318c34938b12e22cb9

component238_lifecycle_evidence_v2.json
ac68b8cc938dc56288c9db7fa9a41d8a64f84fdd353fee6ff3414f6c35e0424b
```

各集合包含重複指令及共用 helper，不將數字相加作為全遊戲覆蓋量。八槽增量只是已知陣列的算術，完整 consumer 集合、新配置與多人執行都仍未驗證。

## 已交付與核對

| 支線 | 正式證據 | 驗證內容 |
|---|---|---|
| 九個參考 player 元件 | [player_component_capacity_evidence.json](player_component_capacity_evidence.json) | 重播成功；獨立代理對原始 capture 核對九個 callback 的 428 條指令、18 條登錄指令，並完整解碼 4,255 指令 initializer；七個護欄及五個新增布局公式吻合。 |
| 本地 player 建立 guard | [local_player_creation_gate_evidence.json](local_player_creation_gate_evidence.json) | 獨立代理未使用原 replay 的 CFG 函式，從六段 unwind fragments 重新建立 565 指令、36 jump、595 edge 的正常 CFG；accepted 邊支配 handle／FDC140 的結論成立；額外 pins、257-byte ready helper 及字串吻合。 |
| 元件 239 生命週期 | [roster_property_apply_evidence_v3.json](roster_property_apply_evidence_v3.json) | 主代理以原始 capture、快取的完整 unwind 解碼及已證入口 leaf 核對 467 筆指令記錄，去重為 379 個位置；八個根的 fragment SHA、字串及兩段完整 32-byte 交換相符。 |
| network index 下游 | [roster_index_usage_evidence_v2.json](roster_index_usage_evidence_v2.json) | 主代理獨立核對 523 個不同指令位置的 bytes／SHA／asm／unwind root、全部選定 block SHA 及三個字串；重讀父子物件來源、index 地址計算及相鄰欄位用途。 |

元件 43 沒有 creation params 首 byte 分類分支。獨立審查提出此文字精度問題後，findings 已修正為 43 共用路徑、其他具分類元件於分支合流後寫入；數字與證據 JSON 未變更。

詳細獨立審查：

- [元件容量審查](player_component_capacity_review.zh-TW.md)
- [本地建立控制流程審查](local_player_creation_gate_review.zh-TW.md)

## 固定輸出 SHA-256

```text
player_component_capacity_evidence.json
4dedec98d7759d1f629500c42bb9a70ff611d0e0b73175e36f2c0306c37f8147

local_player_creation_gate_evidence.json
d101ffbca1faa03318de87424acdfafee58a0d3b86f4f51e9216244a0f5c166a

roster_property_apply_evidence_v3.json
d0dd9c02db933c20801a366d9668131734a29106e46f8a8a0d0de43981a27d22

roster_index_usage_evidence_v2.json
d7098a7d698aa7daaf53e89c08b19cb01e243860f70fbba518690837baf121ee
```

指令數來自不同證據集合，彼此可能重疊，不應相加宣稱不同程式位置的總數。這些核對證明離線分析可由固定資料重建；不證明當前 runtime callback、資產清單、五人加入或八人玩法。

## 研究與實作的界線

- 七個四筆 callback 與參考 player 清單的關係已確認；目前安裝資產解密後的等同性及實际 callback 執行未直接觀察。
- 第五個 index 在 tag DA 的寫入衝突是條件式位址推導；未在實際第五位玩家上觸發或觀察。
- 完整 CFG 限定正常入口及正常返回的 calls；未涵蓋所有 callees、例外或其他建立入口。
- 五／八人 Mod 尚未完成。擴容方案仍需處理同一元件的初始化、搬移、移除、其他讀寫者及外層物件布局。
- 前三次限定擷取已完成。新的 `EXE+0x1ae380` 單一下游工具仍待另一次授權；本輪未執行它。
