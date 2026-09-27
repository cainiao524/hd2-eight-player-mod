# 八人Mod實作工作清單

## 目標與目前狀態

依使用者更新的目標文件：完成八個獨立帳號、八名真人在同一任務合作的可安裝Mod，交付原始碼、版本／安裝／移除說明與可核對實測。第五人是中途驗證點。

目標來源：`C:\Users\OvO\.codex\attachments\9cdd3dbc-0dfd-4f1e-ac64-c2489e52f0cc\goal-objective.md`。本清單保留該文件A至E的完整驗收範圍；沒有把研究或候選元件當作完成。

目前A加入、B角色、C同步、D任務流程均無五人／八人通過證據。E交付僅有離線候選元件及其測試，沒有可安裝八人Mod。

目前已完成下列可支援實作的工作：

- [三S模板v3](indexed_float_pool_triple_members_findings.zh-TW.md)已重跑及複核，確認條件式轉換餘量與partial後同ID不重試；停止重複核對已固定的這批指令，除非版本／依賴／具體風險改變。
- [配置前檢查候選原始碼](../eight_player_candidate_20260927/Source/pool_preflight.lua)已在獨立LuaJIT執行並通過[風險測試](../eight_player_candidate_20260927/verification/pool_preflight_tests.json)。它計算原順序的完整配置峰值、保留其他owner占用、拒絕不一致／同ID partial狀態；尚無遊戲連接層。
- [二進位 snapshot 候選](../eight_player_candidate_20260927/Source/pool_snapshot.lua)已完成提供 bytes 的 bitmap／indices／template／context 與區域重疊核對，接上 preflight；[20 組測試](../eight_player_candidate_20260927/verification/pool_snapshot_tests.json)通過。獨立審查指出的 free payload 漏檢已重現並修正為 constructor／cleanup 雙模式。驗證器不負責讀取 live 資料或提供執行許可。
- [已知 owner 清單候選](../eight_player_candidate_20260927/OWNER_LAYOUT.zh-TW.md)已把 constructor／cleanup 投影轉成 305／325 個地址的規劃與 packet 覆蓋檢查，保留其他 285 個 S；不依 active count 裁掉物件。清單成功後仍需 snapshot 驗 bytes，沒有將新地址視為已配置。
- [20 筆雙 S](indexed_float_pool_double_records_findings.zh-TW.md)、[七個單例](indexed_float_pool_singletons_findings.zh-TW.md)及 [ID0](indexed_float_template_zero_findings.zh-TW.md)的有限來源已完成重跑與審查。雙 S 主模板為一格、七單例固定模板子集合條件式至多 12 格；第二 S 保留狀態、全域共存與 ID0 實際資料仍須核對。不能把這些子集合預算直接加總成無條件全池上界。
- [Roster 原生 receiver 候選](../eight_player_candidate_20260927/NATIVE_RECEIVER.zh-TW.md)已實作 x64 bytes 產生器：固定 303-byte body 的 map／copy／cursor 保留，目的地改接八份 property storage，ordinal／binding 不符轉到明確的 reject continuation。這不是純資料模型；但尚未提供可啟用的 caller hook、reject handler、unwind 或其他 roster 存取改接。
- [Producer 與共同建置候選](../eight_player_candidate_20260927/NATIVE_PROPERTY_PAIR.zh-TW.md)已完成：原 578-byte body 的配置／八 descriptor 行為保留，首次配置前加 guard，property 與 receiver 共用 B。10 組／54 次 x64 執行與 4 組 pair 建置測試通過；資料橋測同 S／跨 S、不同 ordinal 保留 network index。真實 allocator、serializer／transport 與其餘 consumers 尚未整合。

- [四組完整搬移與共同建置](../eight_player_candidate_20260927/NATIVE_ROSTER_BUNDLE.zh-TW.md)已完成：原 `60C410` 的四組 copy 共同改接 `680h` 八格儲存，map 保留原 S；新增 11 組／103 次指令執行通過全部八格搬移及 producer→move→receiver。已查明全零不等於原生初始化；活記錄需保留 opaque bytes，其他 caller／初始化／生命週期仍缺。

- [四插入原生候選](../eight_player_candidate_20260927/NATIVE_ROSTER_INSERT.zh-TW.md)已完成八格改接及 9 組／515 次指令驗證，包含持續八筆與插入→屬性串接。保留 map 有效／新key／同步前提；dense 的 D==T 是新增保守限制，實際 caller／pending 契約未完成。

- [原四格整理反例](roster_compact_counterexample.zh-TW.md)已確認 `P≤D≤T` 不足以保證原 `60CC70` 保留所有 tracked 實體；35 種合成分段有 10 種失去原 D 及 map 一致性。原插入／整理 bodies 的合成序列亦重現，但真實 dispatch 可達性未證。沒有新增 compactor 或把反例調查計入候選通過數。

- [八格分類候選](../eight_player_candidate_20260927/NATIVE_ROSTER_CLASSIFY.zh-TW.md)已完成移入／移出方向 guard 與 88 個 array operands 改接，共同建置十一函式；原語義、暫存協定、原四格對照及分類→新 ordinal 接收已核。外層 caller flag／通知回復、primary 有效性與真實配置仍缺。

- [網路索引 getter 候選](../eight_player_candidate_20260927/NATIVE_ROSTER_GETTER.zh-TW.md)已把單一完整 ID→ordinal→network-index reader 接共同 B，保留 full DWORD／missing／pending，並拒絕越界 active ordinal 與 empty-key 假命中；分類及移除後讀值已核，共同建置十二函式。其他 reader 與完整生命週期仍缺。

- [移除前處理的完整來源](roster_departure_native_findings.zh-TW.md)已固定六個直接陣列讀取及必要 `606820` reader；[三個原指令案例](roster_departure_native_probe_results_v2.json)重現 pending 移除前兩個通知傳 D−1、後續實際移除卻保留 D，D=0 時另有無號下溢。v2 使用 `7FFF` 並執行真實關聯查找的 null 分支，取消原強制 null 替身；其餘通知仍為明示契約。[必要前提](roster_departure_native_prerequisites.zh-TW.md)確認原 `94C9C0` 把輸入 count 限制至 1..4，繼續傳給 `94BE10`；後者的完整局部用途已由下述 v0.11 研究與候選收束。原 caller 是否可達 pending、通知期間狀態穩定與正確 departure 計數契約仍未證；後續 v0.12 採明示候選政策，沒有將這三個來源調查案例列為候選通過數。

- [v0.11 獨立 player_count 原生候選](../eight_player_candidate_20260927/NATIVE_PLAYER_COUNT.zh-TW.md)已完成 `94C9C0` upper clamp 4→8，以及 `94BE10` 僅在 `max==4 && min<=4` 時以 8 作比較上界；tech level、其他 ranges 與原 override 保留。它是兩處原位修改加 51-byte 跳板的獨立模組，v0.11 當時的 roster 共同候選為十二函式。[7 組／188 次驗證](../eight_player_candidate_20260927/verification/native_player_count_tests.json)包含 162 次完整 filter 及 26 次 context 前綴觀察：count1..4 相容，有效 legacy profile 的新5..8 對照原4一致。Source 與 oracle 雙審查完成；真實資產、完整 context 的15個 calls／通知、配置與生命週期仍未驗；此模組單獨使用時仍會把 `FFFFFFFF` 轉為8，不會自行修正 departure 的 pending 下溢。

- [v0.12 完整 departure 候選](../eight_player_candidate_20260927/NATIVE_ROSTER_DEPARTURE.zh-TW.md)已將完整 `605950` 六處陣列讀取接共同 B，並把該 body 的 `606820` callsite 改接既有 getter；原三個 primary 清理、關聯資源、manager、通知次序及尾跳保留。首次可能回呼前核 binding／map／ordinal／pointer／counts；兩個預測通知採新增 `D−(n<D)` 政策，尾部仍讀當時 held S 的 D。共同產物為 **十三個 roster 函式＋獨立 player_count patch 計畫**，53 個已知區域共同核對。[7 組／43 次 top-level 指令驗證](../eight_player_candidate_20260927/verification/native_roster_departure_tests.json)通過，其中7次原版、16次候選為完整 departure，另有17次入口拒絕、1次 remove及2次 getter串接；不代表43次完整 departure 或全部分段窮舉。[靜態審查](../eight_player_candidate_20260927/verification/native_roster_departure_review.zh-TW.md)完成；真實 caller／pending 可達性、跨回呼至實際移除的狀態序列化、資源契約、reject handler／hook／unwind仍缺。

- [v0.13 registry 更新候選](../eight_player_candidate_20260927/NATIVE_ROSTER_REGISTRY_UPDATE.zh-TW.md)將完整 `B54E00` 與必要 `606520` 共八處 array 基址接到 B；保留 registry/global S 的獨立來源、D 範圍、entity-ID 與其他 tags 行為。只有 roster 分支查 binding/counts，匹配後拒絕無效或與 property ordinal 不一致的 map 結果。共同產物含十五個 roster 函式及既有 count 計畫；[8組／87次有界指令驗證](../eight_player_candidate_20260927/verification/native_roster_registry_update_tests.json)含原版12、候選完整返回49、候選拒絕26，真實FD9BA0／606520與其他明示callee替身分列。真實 context-map、資源、同步、handler/hook/unwind 等整合前提未解除。

## 最小必要阻礙與下一個動作

- [完整分段移除候選](../eight_player_candidate_20260927/NATIVE_ROSTER_REMOVE.zh-TW.md)已完成兩 ABI 的刪除前讀查、四陣列改接及新增 pending 尾端補位，共同建置擴為九函式。9 組測試核全部分段、原基準、拒絕及持續重加／接收；獨立 source／oracle 審查完成。完整 caller、外部資源／同步及原 `60CC70` 整理缺口仍未解除。

| 優先項／成品行為 | 目前證據 | 缺口與下一個具體動作 | 停止追查／通過條件 | 外部依賴 |
|---|---|---|---|---|
| P1：額外帳號通過平台加入，對應A | [平台保存結果](REPORT.zh-TW.md#平台建立參數與本機列舉限制)：有八使用者／裝置配置形狀；本機仍有四人guard | 缺具名介面、其他平台房間限制與非同步完成結果。維持已準備的有限介面核對，先定位決定加入結果的回傳／拒絕來源 | 有可辨識的成功／拒絕路徑及其限制；原型階段再以第五帳號確認，最終八帳號通過 | 新live操作須既有或新增明確授權；多人帳號與服務回應 |
| P2：第5–8名建立原生角色，對應B | [本地建立guard](local_player_creation_gate_findings.zh-TW.md)、[單一介面](spawn_interface_findings.zh-TW.md)已接到EXE+1AE380 | 下游loaded code缺失。第四次單一下游工具已備妥；有明確答覆後才依固定範圍執行，之後先判定allocator與有效handle條件 | 能設計有效角色建立／移除的原生變更；第五人角色在各端可見、可控才算實測通過 | 第四次擷取待答覆，不重問、不執行；後續載入／修改授權及多人 |
| P3：八份peer／roster與ID映射，對應A/B | [v0.13 十五函式共同候選](../eight_player_candidate_20260927/NATIVE_ROSTER_REGISTRY_UPDATE.zh-TW.md)加入完整 registry 更新與關聯ID查找，同一 B／count 計畫共同核區域；整理與真實 caller 缺口保留 | 下一個有限離線切點是既有 consumer 清單的完整 `6054F0..605947`：核清 network-index property 讀取、其他 roster 陣列、palette／玩家數通知與必要 helper 契約，再接共同 B。足以形成候選或定位具體外部缺口便停止；不展開無關 callee，也不重查已收束的 B54E00／606520。 departure回呼序列化、其他讀者及配置／發布／清理、整理／caller、真實context map與資源、hook／unwind仍缺 | 完整6054F0有限改接、必要契約與有界原指令對照足以形成候選，或定位具體外部缺口即停止；不當成完整生命週期 | 6054F0完整body已保存，可離線分析；平台、角色、同步與多人仍需外部條件 |
| P4：固定玩家元件及其他玩法資料八份，對應B/C/E | [儲存設計](PLAYER_COMPONENT_RELOCATION_PLAN.zh-TW.md)已區分七個固定容量與兩個可保留的動態元件 | 固定布局逐項完成大小／對齊、建立、搬移、registry副本與cleanup適配；metadata／stack／裝備／tag73／tagDA共同收束 | 每份擴充資料具備完整配套且跨元件索引一致；不以單一writer測試代替完整生命週期 | 離線可先實作／建置；hook時點與執行驗證仍需資料 |
| P5：節點配置與資源所有權不因八人破壞，對應B生命週期/E穩定性 | owner layout、snapshot validator、preflight 已有候選；[第二S有限來源](indexed_float_double_secondary_findings.zh-TW.md)與[整合時點邊界](native_integration_boundary.zh-TW.md)已收束 | 第二S配置來源及引擎排他仍缺。保留實際占用；只有可接合的新來源／同步證據才重開這兩條支線，不再泛查callee或增加同型模型。ID0需實際count0與資源契約；update返回後只能後驗，不算preflight | 完整共存需求與轉換餘量有根據；實際operations、snapshot與executor處於同一有效執行保護，外部資源恢復可證 | 需要具體來源／scheduler／callback／生命週期證據；新的live操作另需明確授權 |
| P6：逐玩家更新、UI、音效與rank，對應C/E | 四格stack／metadata、三項rank資源及缺local已列[設計稿](PLAYER_COMPONENT_RELOCATION_PLAN.zh-TW.md)；v0.11 已完成 count 上限8及有效四人 ranges 延伸，v0.12 已共同建置 departure 與 count 計畫 | 同時改接暫存與讀者；為0..7及缺local明確定義rank／音源。departure 的兩個預測通知已有候選政策，但 `94C9C0` 完整 context15calls／通知及真實 profile 尚未端到端執行驗證；真實資源與回呼期間狀態契約仍缺。`60C2A0` 的數值 fallback 不證明四種以外的命名資源存在，不杜撰hash；原 tech-level 權重索引不作玩家數擴容 | 所有已知索引路徑有八份空間與明確缺值行為；下游玩家數與資源對應在真實資料有效，音源及UI在各端實測一致 | 原始碼可離線；實際資源／音源隔離仍需驗證 |
| P7：整合第五人原型，對應A–D | 尚無可玩的五人原型 | P1–P6達到足夠證據時整合版本guard、初始化／存取／cleanup；準備具體變更清單及診斷，再做四人基線與第五人全流程 | 加入、生成、相互可見、移動／戰鬥／互動、死亡／增援、離隊／重連、撤離／結算逐項有紀錄 | 載入及修改授權、五位玩家／帳號；目前不能安排 |
| P8：六至八人與交付，對應A–E完整驗收 | 未開始實測 | 第五人全流程通過後逐步增加人數，驗證狀態一致性、負載、房主轉移與進度；封裝安裝／移除／恢復文件 | 八帳號同場全流程與穩定性記錄齊全；可重現建置、支援版本、安裝及恢復均可核對 | 六至八位玩家／帳號、各客戶端紀錄及執行條件 |

## 候選元件與成品驗收的關係

`pool_owner_layout.lua`、`pool_snapshot.lua` 與 `pool_preflight.lua` 推進 P5 的已知清單完整性、提供資料驗證、配置前決策與失敗診斷。`known_owner_addresses_complete` 限已盤點地址，不驗 bytes；`consistent_supplied_bytes` 限提供的 bytes 關係；`fits` 代表給定 snapshot 與模板數量下的算術可容納。所有結果 `executable=false`，因為一致 snapshot、引擎同步與 executor 尚未接上。版本欄位相等也不代表已讀取或驗證實際遊戲映像；即使所有 occupied node 都在清單內被認領，也未證明清單外沒有舊副本。詳見[清單契約](../eight_player_candidate_20260927/OWNER_LAYOUT.zh-TW.md)及[bytes 契約](../eight_player_candidate_20260927/SNAPSHOT_CONTRACT.zh-TW.md)。

P5不可因這個元件的單元測試通過而標完成，更不能抵銷P1/P2的整體可行性缺口。整池256／512等容量尚未選定。

## 授權與等待狀態

- 前三次各一次擷取已使用完畢。
- 已提出的第四次`EXE+1AE380`擷取目前未見明確答覆；輸出仍不存在。保持原問題待處理。
- 目前工作限已授權離線分析與工作區候選開發。沒有查詢遊戲程序、載入、注入、寫入程序或修改安裝檔。
- P3 整理與 append reader 的有限缺口需具體新來源才重開。既有移除、分類、getter、player_count、departure與本輪registry更新候選已完成，未變依賴不重跑。下一個有限離線切點是既有 consumer 清單的完整 `6054F0..605947`：核清 network-index property 讀取、其他 roster 陣列、palette／玩家數通知與必要 helper 契約，再接共同 B。足以形成候選或定位具體外部缺口便停止；不展開無關 callee，也不重查已收束的 B54E00／606520。 本輪到共同建置與有限驗證收束，不啟動下一切點。P5維持需新來源才重開的邊界，P1/P2仍是可行性優先門檻；本輪不重問授權、不執行新capture。

## 每項研究的開工與結束規則

新增研究前在對應P項寫清：要修哪個行為、會改變哪個程式決策、拿到什麼便停止、如何接到候選變更／驗證。已固定且已核對的證據只因具體依賴變動才重跑。剩餘外部條件不足時完成獨立工作；若已無有意義的獨立工作，按目標管理規則如實處理受阻。
