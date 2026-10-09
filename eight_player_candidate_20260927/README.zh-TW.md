# 可配置多人容量候選：名冊原生程式與資源檢查

## 目前新增：容量設定與選單邊界

新增 [player_capacity_contract.lua](Source/player_capacity_contract.lua) 與
[player_capacity_menu.lua](Source/player_capacity_menu.lua)。前者是共用的
4/5/8/12/16 容量契約，會計算 `effective_max_players`、驗證 host authority、
任務中升降容量、版本 metadata、pending/apply/rollback 與診斷狀態；後者以
Bingus Shared Loader 啟動，註冊 Mod Options Menu 的 `Player Capacity` 頁。

選單可以顯示設定上限、已加入人數、可用槽位、有效上限、房主權限、客戶端
相容性與設定狀態。Native bridge 尚未通過固定 build 的 ABI／owner lifetime／
quiescence 門檻時，選單只保留診斷並拒絕改動遊戲容量。

新增 [Native/CapacityContract](Native/CapacityContract) 是 Lua、Session／Party
adapter 與 Native bridge 的 C ABI 邊界，支援 1～16 的已驗證容量、組件容量取最小值、
任務中升容預留、任務中降容拒絕及房主權限檢查。這是離線契約測試，不能替代真實
Session、Peer、Player Clone 或八帳號任務驗收。

## 接納契約（離線，未併入 v0.14 收據）

`Source/eight_player_capacity.lua` 是與 v0.14 候選並行的八槽 admission state model。它只驗證 build profile、network index、stable ordinal、pending／active resource bind、generation token、remove hole、反向 map 和 detached snapshot；沒有 FFI、程序存取、原生 hook、PlayFab／Party 呼叫或安裝行為。Python 離線鏡像與契約說明見[八人容量與接納契約](../five_player_feasibility_20260927/EIGHT_PLAYER_CAPACITY_CONTRACT.zh-TW.md)。

## `0.14.0-offline`：6054F0 狀態更新接入共同八格儲存

[狀態更新候選](NATIVE_ROSTER_ARRIVAL.zh-TW.md)已完成離線交付收尾：完整 1111-byte 原 body 產生 1917-byte 候選，19 個 pointer／primary／aux／property 位點改接共同 B；入口檢 binding、counts、map、ordinal、target 與 caller-state。原四列 palette 及 network index≥4 的白色 fallback、三處 current-D 通知、frame／cookie／calls 保留。`arrival` 只是檔名，此函式沒有 append 或 count 遞增的證據。

[5 組／42 次指令驗證](verification/native_roster_arrival_tests.json)包含原版完整返回4、候選完整返回21、入口拒絕17；巢狀 FD9AF0 的25次另列。19處靜態核對、17處有效域動態檢查，6056C8／6056D6只有靜態覆蓋。[Source審查](verification/native_roster_arrival_review.zh-TW.md)及[接續 oracle 審查](verification/native_roster_arrival_test_review.zh-TW.md)已保存；接續重跑42筆紀錄與凍結報告相同。

共同 bundle 為 **16個 roster 函式＋原 player_count 計畫、62個已知區域**，內嵌 v0.13 產物相同。累計 **149組／4,314次套件執行或觀察**，包含原版、拒絕、前綴觀察與預期反例，不能稱為候選成功次數；重跑與巢狀helper不重複計數。15個既有來源與14份舊報告未改，舊套件未重跑。

Sidecar配置／發布／清理、其他reader、caller／callback同步、真實資源、reject handler、hook／Windows unwind仍缺；目前不可安裝，五至八帳號同場任務未驗證。後續P3的[1277920有限調查](../five_player_feasibility_20260927/roster_mask_reader_findings.zh-TW.md)已固定兩個roster讀取與mask前綴：primary+24h和property+Ch都需改接B；24次原前綴觀察未見mask分支造成後續狀態差異，不列入交付套件數。下一步是明確入口guard／普通missing政策並實作完整reader候選。

**目前是可離線執行的候選原始碼元件，尚未接入遊戲，也不是可安裝的八人Mod。** 完整目標與優先工作見[工作清單](../five_player_feasibility_20260927/IMPLEMENTATION_WORKLIST.zh-TW.md)。

## 歷史：`0.13.0-offline`：登錄表更新與關聯 ID 查找共用八格名冊

新增 [roster_registry_update.py](Native/roster_registry_update.py)與[契約／建置說明](NATIVE_ROSTER_REGISTRY_UPDATE.zh-TW.md)。完整 `B54E00` 的六處 pointer／aux／property 存取，連同 tag73 必要 helper `606520` 的兩處讀取，一起改接共同 B。helper 返回 entity ID，保留只查 D 筆及 associated ID `7FFF` 跳過的原語義；不以 network-index getter 代換。

僅在使用 roster 的分支檢查 S 身分與 `P≤D≤T≤8`；tag69 匹配後再查 map 容量／key／ordinal，避免原 missing index 仍進入 aux 寫入。保留其他 tags 的原呼叫與副作用，以及 entity bit0 決定 property flag 的原規則。共同建置現為 **十五個 roster 函式＋原 player_count patch 計畫**，59 個已知區域通過交疊核對；內嵌 v0.12 產物保持相同。

[8 組／87 次頂層指令驗證](verification/native_roster_registry_update_tests.json)通過：12 次原版完整基準、49 次候選完整返回（root 32、helper 17），另有 26 次候選拒絕（root 20、helper 6）。真實 FD9BA0 與候選606520執行原／改接指令，其他tag的資源calls使用明示 ABI 與副作用替身；巢狀helper不重複加入總數。測試包括八格、只掃dense、其他tags、查找拒絕及先前registry副作用不回滾。

引擎端的儲存生命週期、同步、真實 context map 與回呼資源仍是前提；晚拒絕不能撤回較早 registry 項目的副作用。没有安裝、遊戲執行或真人八人驗收。

## 歷史：`0.12.0-offline`：八格離隊前清理與計數

新增 [roster_departure.py](Native/roster_departure.py)與[契約／建置說明](NATIVE_ROSTER_DEPARTURE.zh-TW.md)。完整 `605950` 的六個陣列讀取接到共同八格 B，額外 network reader 改呼既有 getter，保留原資源／關聯物件處理與通知次序。入口先核 binding、map、ordinal、target pointer 及分段狀態；兩個預測通知使用 `D−(ordinal<D)`，pending D=0 不再產生 FFFFFFFF。尾部仍保留原 current-D 讀取。

[7 組／43 次驗證](verification/native_roster_departure_tests.json)分為 7 原完整 departure、16 候選完整 departure、17 候選入口拒絕，以及 3 次候選移除／getter 串接。三個 primary 清理與兩個關聯查找實際執行原指令，其他未展開資源／通知用明示契約。新共同產物含十三個 roster 函式及原 v0.11 player-count patch 計畫，跨元件區域已核對；兩份原嵌入產物保持一致。

這修正的是候選有效狀態下的讀取與計數。從入口至回呼和實際移除之間，仍需引擎層保證名冊狀態與儲存生命週期；入口檢查不提供同步、重入處理或資源失敗回復。沒有遊戲整合或真人驗收。該輪選定的 B54E00／必要 606520 已由上述 v0.13 改接；6054F0狀態更新已納入v0.14。[1277920有限查核](../five_player_feasibility_20260927/roster_mask_reader_findings.zh-TW.md)已固定完整body與兩個roster讀取，mask迴圈未提供已證拒絕結果。下一動作：在原input+10h計時store前定義guard，同時保留普通missing返回，將primary+24h與property+Ch接共同B，完成原指令對照與caller／helper契約；不擴搜無關callee。

## `0.11.0-offline`：玩家數保留至八與設定範圍延伸

新增 [player_count.py](Native/player_count.py)及[原生契約](NATIVE_PLAYER_COUNT.zh-TW.md)。原 `94C9C0` 的 count clamp 上界改八；原 `94BE10` 只把 `max==4 && min<=4` 的設定上界視為八，保留其他 min/max、override、tech level 與權重索引。這是 5-byte／6-byte 兩處原位修改及 51-byte 跳轉片段的離線計畫，尚無安装／unwind／共同修改執行器。

[7 組驗證](verification/native_player_count_tests.json)包含 162 次完整 filter 執行與 26 次 context 前綴觀察。原 count1–4 對照保持，合法四人設定域中的新 count5–8 與原 count4 輸出一致；未把合成設定當成真實資產／遊戲平衡。名冊十二函式 bundle 保持原版本的內容，新增元件尚未與離隊通知及所有 caller 整合。既有十二個候選來源與十一套報告未改，未重跑舊套件。

上述 v0.12 已接合移除前六處資料讀取、額外 network reader 與新的分段計數政策；完整名冊生命週期、執行期同步、平台加入、角色建立及八帳號驗收仍未完成。

## `0.10.0-offline`：換位後讀取正確玩家的 network index

新增 [roster_getter.py](Native/roster_getter.py)，將完整 `606AD0` getter 的唯一 property 讀取接到共同八格 B，成為十二函式共同候選。保留 ID→ordinal→network index 的關係、完整 32-bit 返回值及原普通 missing return；錯誤 binding、無效 active ordinal 與空 bucket 舊 value 假命中先拒絕。Pending 成員不因位於 dense 之外被拒。

[7 組／84 次指令驗證](verification/native_roster_getter_tests.json)通過：73 次候選／串接、10 次原基準／missing、1 次預期原 phantom-hit 重現。分類後 ID 67 從第 7 格移到第 2 格，再經真正原生 map-delete／候選 mover 移到第 1 格，getter 始終讀回同一高位 network DWORD；被刪 ID 返回 missing。詳見[getter 契約與建置](NATIVE_ROSTER_GETTER.zh-TW.md)。

其他讀取端、移除前處理、完整配置／發布／清理與執行整合仍缺。[移除前處理調查](../five_player_feasibility_20260927/roster_departure_native_findings.zh-TW.md)已固定六個直接讀取、額外 reader 及通知順序；原四格合成執行重現 pending 的通知 D−1 與實際移除後 D 不同，且下游另有 1..4 count 限制。該輪沒有新增 departure emitter。後續 `94BE10` 的 count 用途與局部八人政策已納入上述 0.11；平台加入、角色建立與真人任務驗收維持完整目標中的優先缺口。

## `0.9.0-offline`：八格分類切換

新增 [roster_classify.py](Native/roster_classify.py)，將分類移入／移出兩個完整 body 接到同一八格儲存，形成十一函式共同候選。先檢查身分、兩種 sentinel、分類方向與 caller 過渡旗標，再保留原 map／count／暫存呼叫。移入只清零目的 primary、其餘三組交換；移出才完整交換四組，沒有混淆兩種語義。

[分類契約與建置方法](NATIVE_ROSTER_CLASSIFY.zh-TW.md)記錄新程式、[指令測試](verification/native_roster_classify_tests.json)及兩份審查。7 組／853 次執行通過（783 候選／串接、70 原四格基準），以明示契約模擬暫存 helper，包含八格合法分段、原四格對照、拒絕與連續分類→換位後接收。這沒有證明真實 allocator 或外層 caller 成功；配置失敗不是原子操作，拒絕也不會回復進入本函式前已改的旗標／通知。

`606AD0` getter 已納入上述 0.10；其他 readers、原整理缺口及配置／發布／清理、外層 reject／unwind／hook、平台加入、角色建立與多人任務仍待完成。

## `0.8.0-offline`：完整分段移除與重新加入

新增 [roster_remove.py](Native/roster_remove.py)，將兩個移除入口接入共同八格儲存，刪除前檢查 ID／ordinal／prefix flag，並在 dense 移除後補回原程式遺漏的 pending 尾端。它支援全部有序分段，沒有把 D<T 一律拒絕；額外補位是新增候選語義，外部 ownership／caller／同步仍須整合驗證。

[9 組測試](verification/native_roster_remove_tests.json)通過 2,293 次模擬執行：2,141 次候選／串接、150 次原四格基準、2 次預期原程式反例。完整分段的 1,980 次執行核全部 survivor IDs、四組記錄與 map；另通過追加八筆→移除三筆→重新追加三筆→依新 ordinal 接收屬性。詳見[移除契約、修補理由與建置方法](NATIVE_ROSTER_REMOVE.zh-TW.md)。九函式共同範例只產生 bytes，尚未安裝。

`60CC70` 整理與第一張 append 表 reader 的缺口仍保留。分類切換已納入上述 0.9；實際 caller／primary 所有權及暫存成功仍需整合。其他讀者、配置／發布／清理、reject／unwind／hook、平台加入及多人任務尚未完成。

## `0.7.0-offline`：四插入候選與持續名冊驗證

新增 [roster_insert.py](Native/roster_insert.py)，將四個固定插入 body 的直接陣列寫入改接共同八格儲存，保留不同的初始化與 map／count 順序。入口先檢查 binding、T<8 與分段計數；dense 插入另拒絕尚有 pending 尾端的狀態，這個真實 caller 契約仍待完成。

[9 組／515 次指令測試](verification/native_roster_insert_tests.json)通過有效分段、旗標與原四格對照、拒絕、實際 map／mover helper，以及同一名冊連續加入八筆後拒絕第九筆。另實際串接插入→producer→receiver，確認 ID→ordinal 對應；全部使用合成資料，沒有八帳號測試。已完成独立 source／oracle 審查及報告計數修正。詳見[插入契約、限制與建置命令](NATIVE_ROSTER_INSERT.zh-TW.md)。

後續[原四格整理反例](../five_player_feasibility_20260927/roster_compact_counterexample.zh-TW.md)已否定僅憑 `P≤D≤T` 直接改接 `60CC70` 的方案：在 `P<D<T` 且原 tracked 記錄互異的合成狀態，先 P→D、再 D→P 會遺失原 D。35 個計數案例中 10 個失去實體／map 一致性，另以原插入 bodies 的三步合成序列重現；實際 dispatch 可達性仍未證。該輪未加入 compactor，也沒有把 38 次反例調查列為通過測試。追加表 reader 的有限查核尚未接通；pending 所有權需具體新來源才能解除。`60CEA0`／`540A40` 移除已納入上述 0.8；完整 caller、整理、分類、其他讀者、同步、unwind／hook 及八人任務驗收仍缺。

## `0.6.0-offline`：四組完整記錄搬移與三函式串接

新增 [roster_move.py](Native/roster_move.py)，將原 `60C410` 的 pointer、primary、auxiliary、property 四組搬移共同改接八格儲存，保留來源記錄、原 S 與 entity→ordinal map 更新。[roster_bundle.py](Native/roster_bundle.py) 把 mover、producer、receiver 固定到同一個 `680h` 儲存區，property 起點為 B+580h，並檢查跨程式已知區域交疊。

[新增驗證](verification/native_roster_move_tests.json)通過 11 組／103 次 x64 模擬執行，涵蓋全部 64 種八格搬移、原四格對照、拒絕及 producer→move→receiver 的 map 更新串接。独立靜態審查未發現局部缺陷。詳見[共同契約與重現命令](NATIVE_ROSTER_BUNDLE.zh-TW.md)及[審查紀錄](verification/native_roster_move_review.zh-TW.md)。

目前仍缺插入、壓實、分類、移除與其他讀者的改接，以及初始化、發布、清理、reject／unwind／hook。原生初始化有條件分支與非零欄位，不能把全零記憶體視為有效空名冊。四條插入／初始化路徑已納入上述 0.7，移除已納入 0.8；平台加入與角色生成仍是完整可行性的優先缺口。

## `0.5.0-offline`：產生與接收共用八格儲存

新增 [roster_producer.py](Native/roster_producer.py)，從固定 `60C640` 完整函式產生 662-byte x64 候選。它保留 32-byte buffer 配置、八個 property descriptors 與本機 network index 查詢，在配置前拒絕超界 ordinal／錯誤 global roster，將 property 寫入改接與 receiver 相同的八格儲存。

[roster_property_pair.py](Native/roster_property_pair.py) 提供共同建置入口，固定同一 S/B 綁定，並檢查兩段程式、不同 frame 的兩個 reject 入口、原碼及已知 global/helper 範圍的交疊。10 組 producer 測試／54 次 x64 執行及 4 組 pair 建置測試通過；其中資料格式橋實際執行 producer 與 receiver，保留不同 ordinal 下相同的 network index。真實 allocator、網路 serializer／傳輸與遊戲流程尚未執行。詳見[產生／接收共同契約](NATIVE_PROPERTY_PAIR.zh-TW.md)。

此階段的後續搬移與四組陣列改接已納入上述 0.6 候選；其他存取與生命週期仍未完成，這兩段候選不可單獨啟用。

## `0.4.0-offline`：原生接收候選

[Native/roster_receiver.py](Native/roster_receiver.py) 以固定 `60C890` 的 303-byte body 產生 **375-byte x64 候選**，保留原 entity→ordinal lookup、八個 DWORD copy 與 cursor，將符合綁定的 ordinal 0..7 導向八份獨立 property 儲存；超界或 binding 不符會轉到整合者必填的拒絕入口。它重定位唯一外部 RIP 讀取，不會將舊 displacement 直接套用到新地址。

這段已通過獨立靜態審查及 **11 組／52 次 x64 模擬執行**，包括原版對照、非零 cursor、hash collision、拒絕路徑與高位地址邊界。詳細來源、產生方法、實際輸入前提及下一步見[原生接收契約](NATIVE_RECEIVER.zh-TW.md)，審查見[原生候選核對紀錄](verification/native_roster_receiver_review.zh-TW.md)。

候選目前不提供 hook、reject handler 或 Windows unwind 註冊。Producer 已有共同建置候選；其他交換／移除及讀者仍需改接同一份儲存，否則會造成新舊資料分裂；此 receiver 不能單獨啟用。

## 已實作的資源檢查

[Source/pool_preflight.lua](Source/pool_preflight.lua)接收物件／節點池snapshot、已驗證的模板節點數及原本順序的配置操作，回傳：

- 完整配置所需的最高占用與最終占用。
- 第一個空間不足步驟及所缺格數。
- 每步釋放／新增數量，與規劃後的物件狀態。
- 版本欄位不符、無效資料、重複owner、占用不一致、未知模板、同ID partial等診斷。

它保留沒有列入本批操作的其他owner占用，不重排原呼叫，不修改輸入snapshot，也不把空間稍後釋放當作先前配置必定成功。遇到同ID但數量不足，回報需要恢復流程，不偽造成功或自行清除requested ID。

算式來自[已重跑與複核的三S v3證據](../five_player_feasibility_20260927/indexed_float_pool_triple_members_findings.zh-TW.md)，以及已核對的`140C2E0/140C200`行為。候選只計算允許完整配置的條件，不模仿池滿後繼續執行partial變更。

另已實作 [Source/pool_snapshot.lua](Source/pool_snapshot.lua)，直接解析提供的二進位 P／S／node／模板資料，核對 used 與全池 bitmap、每個 active index、模板 element／type／context 關係，以及已知區域重疊。它辨識部分配置，保留未列入操作的其他占用，並拒絕不符合已知 constructor／cleanup 模式的空閒節點。成功後產生標準化 snapshot 交給 preflight。

完整輸入與輸出格式見[二進位資料契約](SNAPSHOT_CONTRACT.zh-TW.md)。這完成提供 bytes 的結構驗證；執行期資料來源、一致擷取、引擎同步及外部 aliases 仍待完成。

`0.3.0-offline` 新增 [Source/pool_owner_layout.lua](Source/pool_owner_layout.lua)，將固定 constructor／cleanup 清單轉成地址規劃與覆蓋檢查：原四份玩家 records 共 305 個已知 S；八份獨立儲存共 325 個，其中 285 個其他 S 保留原地址及順序。它拒絕原地延長八份、整筆 record span 與有限已知區域重疊、漏列已知 owner，以及搬移後仍提供原玩家 storage 的副本；不按 active count 裁掉物件。

整合順序是 `Layout.check_coverage(config, packet)` → `Snapshot.validate(packet)` → `Preflight.plan(...)`。Coverage 成功只證明已知地址清單齊全，會明示 `bytes_validated=false`；後續仍須驗證同一 packet 的實際 bytes。地址可用性、配置來源、外部 aliases 及執行同步尚未完成。詳見[物件清單契約](OWNER_LAYOUT.zh-TW.md)。

## 版本與資料契約

候選針對保存的Windows x64研究profile：Steam build `25480438`，EXE SHA-256 `f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06`，game.dll SHA-256 `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e`。

這是**目標指紋**，不是已在該版本通過八人測試的相容聲明。模組只比較輸入欄位；日後adapter必須從實際映像取得並核對它們。不能直接把`target()`回傳值當成runtime驗證結果。

輸入形式：

```lua
snapshot = {
    version = observed_version,
    capacity = 256,
    used = 255,
    owners = {
        {key = "canonical_S_identity", requested_id = 0x24, allocated = 3},
    },
}
template_counts = {[0x24] = 3, [0x28] = 2}
operations = {{owner = "canonical_S_identity", template_id = 0x28}}
result = PoolPreflight.plan(snapshot, template_counts, operations)
```

示例數字是合成資料。`key`必須是adapter對同一S提供的唯一、標準化身分；每個S只列一次。模板ID限此profile的0..72，每S索引實體上限12。若要請求ID0，adapter必須明確提供`counts[0]=0`；未知或非零的ID0不受此候選支援。這沒有證明目前runtime的ID0已符合條件。

輸入table必須無metatable，owners及operations須為連續的一起算陣列。4096個owner／8192步是這個候選的輸入資源上限，不是遊戲玩家或池的容量。整數運算保留超過u32容量的需求值，不將它截斷成可容納。

### 回傳狀態

| status | 後續整合層應處理的情況 |
|---|---|
| `fits` | 算術可容納；仍須一致snapshot、有效所有權及相同執行保護 |
| `insufficient_capacity` | 不可開始這批原生配置；回報不足步驟／數量，交由尚待設計的容量或恢復流程 |
| `partial_same_id_requires_recovery` | 空間足夠也不會讓原生同ID早退自動修復；需要明確、已核對的恢復流程 |
| `version_mismatch` | profile不符，停止候選適配 |
| `inconsistent_ownership`／`duplicate_owner` | snapshot不能用於正確的釋放與占用計算 |
| `unknown_owner`／`unknown_template`／`invalid_input` | 缺資料或不符合已支援範圍 |

上述三個 Lua 資源元件的結果皆為`executable=false`，沒有FFI、程序操作、loader callback、hook、原生記憶體配置或引擎呼叫。新增 Python 原生產生器只輸出機器碼資料，其 `installable=false`，也不操作遊戲。

規劃結果另標記 `state_semantics="full_allocation_plan_not_native_post_state"`。steps／final_used／final_owners 是假設每一步完整配置成功的預算；即使 status 是 `insufficient_capacity`，也不把原生可能發生的 partial 狀態當作已觀察結果。不得用這些欄位覆寫失敗後的實際資源狀態。

## 接入原型前必須完成的配套

1. 在已核對的時點取得相同 pool、模板與 S 的一致 bytes 與實際版本指紋，依 owner layout 核對已知清單，再交給 snapshot validator。提供清單內的唯一索引已能檢查；外部未提供的 S 副本與 aliases 仍需額外證據。
2. 找到有效的引擎執行緒／同步方式，涵蓋snapshot、preflight與整批配置；兩次讀取一致不能替代排除重入與競爭。
3. 保留原本call順序。不同路徑的主／第二／第三S順序不同，不能只挑選峰值最低的模型來執行。
4. 失敗時如何延期、恢復或擴池，必須有生命週期與事件語義依據；本元件沒有擅自定義skip為正確玩法。
5. 補上原生executor、結果比對與錯誤診斷；在授權及原型具備後，從四人基線到第五人再到八人驗證。

因此，這個候選推進配置失敗處理所需的資料驗證與決策程式，尚未完成上述adapter／executor或任一多人驗收。

## 離線測試與可重現方式

測試使用Python 3.12 Windows x64及[Lupa 2.6](https://pypi.org/project/lupa/2.6/)的`lupa.luajit21`，直接執行候選Lua檔。測試依賴只安裝到本候選的`.test-deps`，未修改其他Mod或全域Python套件。

在工作區根目錄執行：

```powershell
& 'C:\Program Files\Python312\python.exe' -m pip install --disable-pip-version-check --only-binary=:all: --no-deps --target 'eight_player_candidate_20260927/.test-deps' 'lupa==2.6'
& 'C:\Program Files\Python312\python.exe' -X utf8 eight_player_candidate_20260927/tests/test_pool_preflight.py
& 'C:\Program Files\Python312\python.exe' -X utf8 eight_player_candidate_20260927/tests/test_pool_snapshot.py
& 'C:\Program Files\Python312\python.exe' -X utf8 eight_player_candidate_20260927/tests/test_pool_owner_layout.py
```

已有依賴時只需後三行。Python位址不同時使用相同版本與架構的解譯器。沒有遊戲建置／安裝步驟，因為此階段未封裝addon；不應把此資料夾複製到遊戲安裝目錄。

測試涵蓋兩種轉換順序的峰值、其他owner占用、partial／同ID、版本不符、不一致snapshot、未知模板、稀疏或metatable輸入、同owner多次變更、u32邊界及輸入不被修改。最新[測試結果](verification/pool_preflight_tests.json)記錄原始碼SHA、固定證據SHA、解譯器與結果；這是離線元件驗證，沒有替代遊戲測試。

[20 組二進位驗證與整合測試](verification/pool_snapshot_tests.json) 直接以 LuaJIT 執行 Lua 原始碼，包括合成 256 格全占用池在轉換時需 257 格、初始化空物件、未知模板、重複／越界索引、錯接 context、截短、地址重疊及兩種 free node 模式。獨立只讀審查與修正紀錄見[審查文件](verification/pool_snapshot_review.zh-TW.md)。

新增的 [23 組清單與整合測試](verification/pool_owner_layout_tests.json) 以固定 constructor／cleanup 證據產生預期地址，核對 305／325 個完整順序、整筆 record 尾端碰撞、搬移後舊副本、缺失／重複，以及接到 snapshot validator 後拒絕錯誤 pool pointer。獨立審查發現額外 S 可覆蓋目前玩家 record 頭尾的非 S 欄位，已重現並補上完整 span 拒絕；外側相鄰且不相交的地址仍可接受。加上 preflight 的 11 組及 snapshot 的 20 組，現有三組測試套件合計 **54 組通過**。這些測試資料是合成 bytes，並非實際 heap 擷取或多人執行紀錄。

本輪沒有安裝任何遊戲檔案，因此沒有需要從遊戲移除的內容。最終Mod的安裝／移除／恢復說明仍待封裝階段完成。

原生機器碼測試使用本機資料夾依賴，重現命令見各候選契約。既有144組加本輪[狀態更新](NATIVE_ROSTER_ARRIVAL.zh-TW.md)5組，共 **149 組離線測試**；原生套件合計 **4,314 次 x64 執行／觀察**，本輪新增42次的分類見上方v0.14。總數包含原版基準、候選拒絕、兩次預期原移除反例、一次預期原empty-key假命中，以及前版26次僅執行context前綴的觀察；不能稱為4,314次候選成功或完整函式執行。巢狀helper不重複計數，獨立departure／compactor研究探測亦未計入。Pair四組只作bytes組合／區間核對。這些離線結果不替代遊戲與多人驗收。
