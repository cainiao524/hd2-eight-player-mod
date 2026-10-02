# 八槽儲存設計約束：玩家元件與索引下游

## `0.14.0-offline`：6054F0 狀態更新接入共同八格儲存

[狀態更新候選](../eight_player_candidate_20260927/NATIVE_ROSTER_ARRIVAL.zh-TW.md)已完成離線交付收尾：完整 1111-byte 原 body 產生 1917-byte 候選，19 個 pointer／primary／aux／property 位點改接共同 B；入口檢 binding、counts、map、ordinal、target 與 caller-state。原四列 palette 及 network index≥4 的白色 fallback、三處 current-D 通知、frame／cookie／calls 保留。`arrival` 只是檔名，此函式沒有 append 或 count 遞增的證據。

[5 組／42 次指令驗證](../eight_player_candidate_20260927/verification/native_roster_arrival_tests.json)包含原版完整返回4、候選完整返回21、入口拒絕17；巢狀 FD9AF0 的25次另列。19處靜態核對、17處有效域動態檢查，6056C8／6056D6只有靜態覆蓋。[Source審查](../eight_player_candidate_20260927/verification/native_roster_arrival_review.zh-TW.md)及[接續 oracle 審查](../eight_player_candidate_20260927/verification/native_roster_arrival_test_review.zh-TW.md)已保存；接續重跑42筆紀錄與凍結報告相同。

共同 bundle 為 **16個 roster 函式＋原 player_count 計畫、62個已知區域**，內嵌 v0.13 產物相同。累計 **149組／4,314次套件執行或觀察**，包含原版、拒絕、前綴觀察與預期反例，不能稱為候選成功次數；重跑與巢狀helper不重複計數。15個既有來源與14份舊報告未改，舊套件未重跑。

Sidecar配置／發布／清理、其他reader、caller／callback同步、真實資源、reject handler、hook／Windows unwind仍缺；目前不可安裝，五至八帳號同場任務未驗證。後續P3的[1277920有限調查](roster_mask_reader_findings.zh-TW.md)已固定兩個roster讀取與mask前綴：primary+24h和property+Ch都需改接B；24次原前綴觀察未見mask分支造成後續狀態差異，不列入交付套件數。下一步是明確入口guard／普通missing政策並實作完整reader候選。

## 狀態與工作方向

這份文件把元件 33、41、43、238、250 已核對的布局與生命週期整理成實作約束，並補充共用 map、元件 3／260 與索引下游的決策。它是**離線設計稿**；尚未形成完整原生補丁，沒有配置遊戲記憶體、修改指標或驗證八人執行。

下一階段優先核對的方案是：**保留原本內嵌元件物件的地址、header 與登錄身分，另配置八槽陣列，逐一改接所有陣列存取。** 這能保留目前已找到的 owner 直接 count 存取和 registry 指標身分，代價是每個直接位移與衍生地址的陣列读寫都要完整列出並適配。現在的存取清單仍不完整，尚不能稱此方案已可實作或安全。

若改為搬移整個元件物件，則必須額外修改 global、owner 直接地址、registry 保存的副本、取消登錄及內嵌 map 自指標。兩種方式都需要保留以下資料關係與生命週期。

## 1. 已確認的五組布局

O 是原 context+0x40 的 component owner；S 是表中元件物件。每筆寬度均為十六進位，`i` 為元件自身的零起算 ordinal。

| 元件 | S / 下一個已發布成員 | 所有本輪確認的逐 ordinal 儲存 | 四筆增加到八筆的純資料增量 |
|---|---|---|---:|
| 33 | O+`3CA0` / O+`3F58`，間距 `2B8` | pointer `70+8*i`；byte `90+i`；primary `98+50*i`；secondary `1D8+38*i` | `0x244`，580 bytes |
| 41 | O+`4148` / O+`2A930`，間距 `267E8` | pointer `68+8*i`；large `88+9928*i`；兩組小記錄 `26528+58*i`、`26688+58*i` | `0x26780`，157,568 bytes |
| 43 | O+`2A988` / O+`2AE30`，間距 `4A8` | pointer `68+8*i`；record `88+108*i` | `0x440`，1,088 bytes |
| 238 | O+`E9FC98` / roster O+`EA0818`，間距 `B80` | pointer `948+8*i`；byte `968+i`；primary `96C+44*i`；property `A7C+40*i` | `0x234`，564 bytes |
| 250 | O+`EB5178` / O+`EB52E0`，間距 `168` | pointer `70+8*i`；record `90+34*i`；兩組 bytes `160+i`、`164+i` | `0xF8`，248 bytes |

增量按「新增四筆×已知每筆寬度」計算，**不是 allocation 大小、整個 Mod 的記憶體成本或已選定新位移**。對齊、原本 padding、額外管理資料及其他子系統都另計。33 的 `[94,98)` 仍未分類；238 的最後 property 記錄與下一成員相距四個 bytes；這些空隙都不足以容納八筆。

來源：

- [33／250 生命週期，正式 v2](component33_250_lifecycle_findings.zh-TW.md)
- [41 生命週期，正式 v2](component41_lifecycle_findings.zh-TW.md)
- [43 生命週期](component43_lifecycle_findings.zh-TW.md)
- [238 生命週期](component238_lifecycle_findings.zh-TW.md)

### 本輪修正過的兩個未知區域

- 33 的 `+90` 已由分類回呼下游證明有逐 ordinal byte；第五個 pointer 會覆蓋這些 bytes。只有其後 `[94,98)` 仍未分類。
- 250 的 `[160,164)` 已在獨立審查中確認為另一組逐 ordinal bytes，正式 v2 已移除「未知 gap」分類。`+160` 與 `+164` 的搬移規則不同。

## 2. 實作必須保留的規則

### 元件 ordinal 與 network index

這五個元件主要以 entity ID 查自身 map，取得儲存 ordinal。它可能因分類或移除而改變。新陣列的選址應保留這種映射，不能假定 index 4 的網路玩家永遠使用元件槽位 4。

### 移除壓實與分類轉移

| 元件 | 單向搬移 helper | 不能遺漏的差異 |
|---|---|---|
| 33 | `665FE0` | 複製 pointer、兩組記錄並修 map；不搬 `+90` byte。分類移出另有 byte 單向複製。 |
| 41 | `7AF210` | 複製 pointer、大記錄及兩組小記錄；分類移入清零目的大記錄，移出才完整交換。 |
| 43 | `9BA8D0` | 複製 pointer 與完整 `108` bytes，修搬入 entity 的 map value；來源槽未在此清零。 |
| 238 | `87B5D0` | 複製 pointer、`44`、`40` 記錄；不搬 `968` byte。分類轉移另有完整記錄交換及 byte 操作。 |
| 250 | `671610` | 複製 pointer、`34` record、`164` byte；不搬 `160` byte。分類增加會清零目的 primary，分類減少才交換 primary；`160` 為單向複製、`164` 為交換。 |

每條路徑的 count 更新、entity pointer、相關記錄、map value 必須保持一致。這份表不能取代原函式的完整條件分支；異常 ID、空表或越界輸入也沒有被證明可無條件接受。

Roster 239 的後續[原四格整理反例](roster_compact_counterexample.zh-TW.md)另確認 `60CC70` 在 `P<D<T` 時先 P→D 再 D→P，沒有保存原 D。若全部 tracked records 有效且互異，原 D 會遺失；有序 counts 不足以支持直接改接八格。此處仍須釐清 pending／prefix 呼叫及所有權契約，不能把上述其他元件的交換或移除規則直接套用到 roster。

### Header 與 map

各物件已有八個 inline hash buckets，容量代表可探測的 key/value 項數。保存的共用 insertion／deletion helper 沒有另一個四筆負載條件，但沒有自動增容。[八項模型驗證](component_map_capacity_findings.zh-TW.md)已通過 65,536 種 home 分布、逐項刪除／重插／更新及 80,640 種刪除順序；限定指令直譯另與高階模型對照，保存 helper 的所有條件分支兩個結果均覆蓋。

目前方案可保留八 buckets，但必須明確維持：**不同有效 key 最多八個，capacity 非零且為 2 的整數次冪、sentinel 正確、backing 足夠，外層 ordinal 有對應資料。** 第九個不同 key 會進入地址 `0x4` 的無效寫入，不能靠 helper 安全拒絕。這仍是離線模型結論，沒有執行遊戲碼。

整物件搬移仍需修正指向原物件內部的 map pointer。任何 bucket 容量調整都要同時修改 backing、capacity、mask 與初始化；若更改為十六，應有額外成員需求或其他明確理由，不能把它當成八人必需的已證條件。

## 3. 重新指向陣列時的必要範圍

對每個元件，新陣列必須涵蓋：

1. 已登錄 callback 的兩種加入入口及四筆 guard。
2. 實際使用的其他加入 helper，並保留 RCX／RDX 等參數差異。
3. Map removal 後的單向壓實、分類移入／移出及其衍生地址。
4. Property 建立、套用／反序列化，以及後續更新或合併。
5. 直接透過外層 owner 形成 S 的程式；即使 S 不變，內部陣列取址仍須導向同一份新資料。
6. 第一槽特殊讀者，保留其原本條件；不能自行把所有 slot 0 操作改成八次迴圈。
7. 配置、初始化、重設、資源重載、刪除與釋放時點，使新陣列與原物件生命週期一致。

已證 registry 指標副本數為：33 兩份、41 五份、238 七份、250 八份。43 目前已固定的是直接 owner 路徑，沒有在此推定對應 registry tag。這些數目不是全遊戲所有別名的總數。

## 4. 已補上的接收與內嵌存取

### 單一 entity 的 property 格式

[Property 分派](property_dispatch_findings.zh-TW.md)已固定 selector `3A7 → BD138C`。此 selector 來自 API output metadata，沒有證明它等同 wire header 或當前 player 的執行期格式。該分支依序呼叫 250、239、238、33、41，以及 `owner+EB5E10` member，合計消耗 `4+32+64+56+88+36=280` bytes；最後 member 後續已由[元件 260 身分鏈](component260_capacity_findings.zh-TW.md)確認。

各接收器以 entity ID 查自身 map 再選 ordinal，並共用 cursor。重新配置時必須保留完整消耗量，即使某個四 byte 槽只讀一 byte，也不能縮短 cursor。已核對的目的地包括：

| 元件 | receiver | 要改接的目的地 |
|---|---|---|
| 250 | `671860` | `S+164+ordinal` byte；輸入仍消耗四 bytes |
| roster 239 | `60C890` | `S+3A8+ordinal*20` 的八個 DWORD |
| 238 | `87BB30` | `S+A7C+ordinal*40` |
| 33 | `666590` | `S+1D8+ordinal*38` |
| 41 | `7AF610` | **第三陣列** `S+26688+ordinal*58` |

[Roster receiver](roster_property_receive_findings.zh-TW.md)會原樣保存 32-bit network index。此處不需增加位元寬度，也不存在要提高的四人比較。Caller 直接形成各個 owner 內嵌地址；保留 S 的方案仍需修改 receiver 內部目的陣列位址，整物件搬移方案則還要改 caller 的 owner 別名。

有效 ID→ordinal、足夠 buffer、已配置的 record 都是必要前提；callee 沒有自行保障這些條件。不能藉放寬檢查補救未建立的 entity mapping。

### 元件 43 的內嵌更新

[`129FD00` consumer](component43_inline_consumer_findings.zh-TW.md)在 `12A02BB` 直接讀 global 後自行更新記錄。必要變更包括 `12A0402` pointer `+68`、`12A0445` record `+88`、`12A0451/492/4A4/4B3` 的 count `+188` 與由 record pointer 衍生的六處存取。只改獨立 helper `9BA430` 不會涵蓋它。

Record count 是 `record+100`，與以 RDX 保存的 record 起點分開計算；改接時兩者必須指向同一新記錄。`16` 是每筆記錄內項目數，不是玩家數。有限 RIP MOV／LEA 掃描的十個已識別 global 引用已全部分類，仍不代表所有别名與存取都已收齊。

### 其他 index 儲存的新增必要範圍

[雙 float writer](indexed_float_storage_findings.zh-TW.md)的 D 子物件只初始化四筆 `298`-byte records。Network index 4／7 的八 byte 寫入會覆蓋已初始化的相鄰物件欄位。因此整體八人方案還需處理這個 record 區域的配置、初始化、writer、其他讀寫者與 cleanup；不能因為 enclosing allocation 很大就保留原位增加筆數。

[後續有限 consumer 清單](indexed_float_consumers_findings.zh-TW.md)已接上同一 D 的 12 個 roots，增加以下具體約束：

| 項目 | 已確認的約束 |
|---|---|
| Record 空間與遍歷 | 八筆共 `0x14C0` bytes，新增 `0xA60`，是邏輯資料量而非完整配置成本。初始化、清理及多個更新的四筆界限要共同改接。`14329B0` 為兩筆展開、兩次迭代；八筆對應四次雙筆迭代。 |
| 內嵌子物件 | 每筆有五個子物件，方法接收衍生的 interior pointer。原有 owner／pool 回指須保持一致；尚未證明直接 memcpy 足以搬移。 |
| 兩張 metadata 表 | `D+8D6C4` 與 `D+8D6D4` 各四個 DWORD，後方已有使用中欄位。各增四格且共同改接初始化及讀寫；不能各自原地延伸。 |
| Stack 索引表 | `142D870` 的 `[RBP-60,RBP-50)` 只有四格。n=4 未被 local/current 條件跳過時覆蓋稍後仍使用的 `RBP-50` ID；重新布局還需維持 stack frame、unwind、呼叫對齊與所有引用。 |
| Rank→ID 表 | 三張表各三項。八筆中確有一筆被 local/current 條件跳過時最多七項；selected index=-1 時可能有八項。需確認有效 ID 選項，並為缺 local 的狀態設定有界處理；沒有證據可直接杜撰新資源 ID。 |

單筆索引路徑仍需分別保留原有條件，例如 `142FF90` 的輸入需等於選定index。`142EE70`的q已在後續接到confirmed-peer表，詳見下節。此清單證明上述改接是必要的，仍未涵蓋所有aliases、外部helpers或執行期生命週期。

### 後續已確認的 q、資源所有權與音效選項

下列補證確立了額外的配置、改接與清理要求：

- **q的身分：** [來源證據](indexed_float_external_index_findings.zh-TW.md)確認它是按host-selection peer key查得的confirmed-peer network index。Client records改接須處理此處的owner-relative存取；D records改接須包含`142EF8E/142EF9E`。保留no-match／`FFFFFFFF`流程，建立合法`0..7`的索引條件。q不是record ordinal，也不能固定為0。
- **新增實例：** [子物件證據](indexed_float_subobjects_findings.zh-TW.md)確認新增四筆共20個S須各自使用`140C160`初始化；不得複製active S的pool indices。原四筆搬移則須轉移唯一所有權並停用旧位置，保持D／P／外部context有效。
- **共用池：** `P=D+36F8`初始256格；每格`208` bytes，末端已是occupancy區。[指定模板的建立流程](indexed_float_template_budget_findings.zh-TW.md)已把條件式需求收窄為每筆11格、新增四筆44格、八筆88格；前提是執行期模板等同所分析的建立結果。先前240／480格是索引欄位的物理上界。保留256格須證明其他用途與額外暫存合計不超過168格。[初始清零來源](indexed_float_pool_initial_zero_findings.zh-TW.md)已接到外層配置的整塊zero-fill，涵蓋used count／cursor／occupancy；這不證明它們在後續每次constructor時仍為零。擴池時另配node與occupancy backing，並核完整consumer集合。
- **池的建立與重用：** 新S沿用active P時保留原占用紀錄；全新空池才建立零occupancy／used count／cursor，再配置有效pointers與capacity。替換既有池須先閉合資源所有權與aliases，不能在active S仍持有indices時清空P。原首次清零路徑不能作為可重複reset。
- **直接生命週期清單：** [完整建立／清理投影](indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)確認原305個S的位址與順序一致，其中玩家20個、其他直接成員285個。八筆玩家改為40個S後清單為325項；Python獨立儲存情境能使兩條清單一致且無S範圍重疊。只增加迴圈而保留原基底有27組S區間衝突。建立anchor／count `142BB8D/142BB94`與清理`142C9CE/142C9D5`須共同適配；其他20／64／5／32次成員迴圈不因此增加。這只涵蓋兩個roots的直接S呼叫，並非全部aliases或引擎資源釋放證明。
- **保留配置與其他模板：** [可選子物件helper](indexed_float_pool_optional_members_findings.zh-TW.md)的false旗標路徑沒有直接回收相應S，容量需涵蓋尚未cleanup的既有配置。四組主模板`20/21/2F/22`各一格；指定四個callers的需求式為`c20+c21+c2F+2*c22`，在有效counter及模板等同性前提下最多72格。[Counter writer續查](indexed_float_pool_counter_bounds_findings.zh-TW.md)已確認四個清零store與五條有unsigned guard的新增路徑，分別保留1／64／5／1上限；有限掃描之外的aliases仍未排除。這是部分成員的配置要求，不能當作其他285個S的完整生命週期峰值。
- **數量清零與快取：** `142BED0`的無call清零後段有266處D寫入，全不重疊305個S及pool區域；count歸零本身未清理active nodes。`D+8D709`是已定位builder的快取旗標，其他三處旗標writer的完整caller／cleanup關係仍待核。另有`142C8F0`清理候選缺caller身分證據，不先列為已接通回收入口。既有1／64／5／1其他記錄容量不因玩家增加而自動翻倍；三S指定模板分析已完成如下，完整回收／共存來源仍缺。
- **32筆三S與轉換餘量：** [模板來源及v3模型](indexed_float_pool_triple_members_findings.zh-TW.md)已接上`D+886B0` records、`8B6B0`模板表與`8B730` count。已列主模板`24..2C`最後每筆要求3至5格；32筆條件式需求160，分別取三S最大值為192，均不是全池或所有caller上界。保存的call順序可在局部轉換模型形成5→6→5；僅留5格會partial配置，之後同ID不重試。必須證明轉換餘量或設計保留語義的失敗處理，不能只按最後需求配置。Builder含opaque calls，count／模板域歸納有不干擾前提；ID0與全域狀態可達性仍未閉合。Initializer的四次迴圈建立29..2C四種模板，不作玩家容量補丁。
- **其他實體物件與候選清單：** [20筆雙S](indexed_float_pool_double_records_findings.zh-TW.md)主模板1F為一格，第二S保留資源的完整來源仍缺；active count為零仍保留40個實體S。[七單例](indexed_float_pool_singletons_findings.zh-TW.md)的固定模板子集合條件式至多12格，不能當全部舊狀態或整池上界。[ID0](indexed_float_template_zero_findings.zh-TW.md)只在 supplied count0、所有權及事件／資源條件成立後列入單一S清理／恢復計畫。這些結論已接到[owner layout候選](../eight_player_candidate_20260927/OWNER_LAYOUT.zh-TW.md)：四筆305／八筆獨立儲存325個已知S，完整清單再接bytes驗證；尚無原生配置／搬移／回收或同步保護。
- **配置失敗：** `140C2E0`先記requested ID，池滿可能留下partial count，而相同ID下次不重試。方案需保證可用格數或明確处理未完成配置，不能用返回即完成作判準。
- **Rank ID：** [音效證據](indexed_float_rank_ids_findings.zh-TW.md)確認兩組Wwise event與一組float parameter。保存boot表有兩個原參數key缺失；不能杜撰新hash、把0視為已驗證fallback，或把local三值當額外remote選項。新增rank仍需明確對應與音源隔離驗證。
- **可保留的helper本體：** 在D與其他欄位地址不變的前提下，[`142FA60/1432F10`](indexed_float_helper_boundaries_findings.zh-TW.md)沒有直接的本批record／metadata基址要改；caller依然要改接。其他caller情境與API callees不在此結論內。

這些補證使配置與cleanup的要求更具體，尚未定下可直接載入的原生修改。主代理已核原bytes與關鍵語義；自寫helper分析及磁碟擷取的另一代理審查因用量限制未完成，詳見[核對範圍](indexed_float_remaining_review.zh-TW.md)。

## 5. 可保留的既有動態元件

[元件 3](component3_capacity_findings.zh-TW.md)的兩個 qword 陣列初始有 512 筆，map 有 1,024 buckets；[元件 260](component260_capacity_findings.zh-TW.md)的四個資料陣列初始有 64 筆，map 有 128 buckets。兩者加入流程都比較物件 capacity 並呼叫擴容 helper，資料經 heap pointer 存取。

對目前已核對的初始化、加入、搬移及接收範圍，這兩個元件不需要四筆改八筆的容量補丁，候選方案保留原本的動態儲存。實作仍需保持有效 ID、ordinal、count 與資料的關係，不能因資料容量較大便跳過後續相容性驗證。它們是所有 component entities 共用的容量，亦不能當作保證有 512／64 名玩家空位。

## 5a. Roster 分類候選的最新配套

[0.9 分類候選](../eight_player_candidate_20260927/NATIVE_ROSTER_CLASSIFY.zh-TW.md)已把 `60CF50`／`60D300` 接到原 `680h` 八格 sidecar，連同既有九函式共同建置。移入只交換 pointer／aux／property 並清零目的 primary；移出才交換四組。兩個方向保留原兩筆 map 與 count 次序、24-byte scope 的暫存配置／兩次恢復，不能共用無條件四組 swap 假設。

Guard 根據已知 caller 的過渡旗標判斷，沒有改變 entity bit 或派發通知。真實外層 rejection／rollback、暫存成功／無重入、primary 有效性與全域生命週期仍缺；其他尚未改接的 consumer 不能直接與新 B 混用。[0.10 getter](../eight_player_candidate_20260927/NATIVE_ROSTER_GETTER.zh-TW.md)已接同一 B，保留 full DWORD／missing／pending，並驗證分類及移除後的讀值。

### 移除前清理的必要配套

[完整來源](roster_departure_native_findings.zh-TW.md)與[必要前提](roster_departure_native_prerequisites.zh-TW.md)固定 `605950..605F2F` 的兩處 pointer、三處 primary 首 DWORD、一處 property 首 DWORD 讀取；property 首 DWORD 是關聯 entity ID。額外 `606820` 的兩處 property+Ch network-index 讀取也必須共同改接。三個 primary helper 仍須接原 S 作 owner 身分並保留 registration 解除與可能的 backing 釋放；不能把 S 一律替換為 B。

原次序是清理／通知在前、`540A40` 實際名冊刪除在後。原四格有界合成執行顯示兩個通知傳 D−1，尾部 `player_count` 傳當時 D；pending 實際移除則不減 D。`94BE10` 的玩家數局部用途現已核清；v0.12 採用 `D−(n<D)` 作兩個預測通知的新候選政策，與名冊移除的 dense-count 算術一致。這不是原通知契約的證明；pending caller 可達性及回呼期間 map／S／ordinal／counts 是否穩定仍未證。

原 `94C9C0` 對收到的 count 做 unsigned clamp 1..4，再發 `num_players` 並傳至 `94BE10`。[完整局部資料流](roster_player_count_native_findings.zh-TW.md)確認 `94BE10` 只把玩家數與來源 record `+F4/+F8` 的人數範圍比較；鄰近的權重表索引使用另一個 tech level 參數。來源 record 步幅 `118h`，原 override 分支可跳過通常資格檢查。

[v0.11 獨立 player_count 模組](../eight_player_candidate_20260927/NATIVE_PLAYER_COUNT.zh-TW.md)已實作兩處原位修改及 51-byte 跳板：`94C9C0` upper clamp 改為8；`94BE10` 僅對 `max==4 && min<=4` 使用 effective max=8，保留 min、其他 ranges、override 與 tech level。它獨立於 v0.11 當時的十二函式 roster 共同候選。[7 組／188 次驗證](../eight_player_candidate_20260927/verification/native_player_count_tests.json)包括162次完整 filter及26次 context前綴觀察；原count1..4相容，對有效 `1<=min<=max<=4` legacy profile，新count5..8與原count4的選集／輸出一致。Source與oracle雙審查完成。

上述結果未執行完整 `94C9C0` context的15個calls／通知，也未驗真實資產、配置失敗或輸出容量。原0→1保持；player_count 單獨使用仍會把FFFFFFFF轉為8，不能自行修正舊 departure 的 pending D=0下溢。`60C2A0`仍只有1..4命名資源分支，其餘值可走`Multiplayer_NumberOfActiveTeammates`數值通知；不能由此推論第五人被平台拒絕或杜撰新增資源hash。

[v0.12 完整 departure 候選](../eight_player_candidate_20260927/NATIVE_ROSTER_DEPARTURE.zh-TW.md)已完成上述六處讀取與唯一 `606820` callsite 的共同 B 改接；後者呼叫既有 getter，沒有全域替換 `606820`。三個 primary helper 繼續使用原 S，原資源 callback、manager 支線、通知次序與間接尾跳保留。首次可能回呼前 guard 核 target／binding／map／ordinal／counts；frame `80h→90h`，`+60h` 保存 entry 計算的 remainingD，`+64h` 保存 ordinal。兩個預測通知使用 remainingD，pending D=0保持0；尾部仍讀 held S 的當時 D，只有 D不變時才等於 entry D。它需要入口至回呼及真正移除之間的狀態序列化、global S等於held S及storage持續有效；guard 不提供排他、重入安全或失敗回復。

共同產物為 **十三個 roster 函式＋獨立 player_count 的兩處修改／51-byte 跳板**，53個已知區域共同核對；跳板不算第十四個 roster 函式。[7組／43次 top-level 指令驗證](../eight_player_candidate_20260927/verification/native_roster_departure_tests.json)通過，分為7次原版完整 departure、16次候選完整 departure、17次入口拒絕、1次remove及2次getter串接。這是有限代表分段／ordinal與分支案例，沒有窮舉全分段。三個 primary helper及關聯查找執行保存指令，其餘外部資源／通知採明示 ABI與順序契約替身；完整context、真實資源釋放／失敗及外層caller仍未驗。[靜態審查](../eight_player_candidate_20260927/verification/native_roster_departure_review.zh-TW.md)已完成；reject handler、hook、載入版本核對與Windows unwind仍未整合。

[v0.13 registry更新候選](../eight_player_candidate_20260927/NATIVE_ROSTER_REGISTRY_UPDATE.zh-TW.md)已完成 B54E00 六處 array 基址及必要606520兩處共同 B 改接。root的registry S與global S須同一綁定；property迭代ordinal與map結果另驗相同，map miss／invalid不再進aux寫入。guard限定於tag69及tag73使用roster前，保留其他tags、D範圍及原flag判斷；606520返回entityID而非network index。新共同產物十五個roster函式、59個已知區域；player_count計畫及內嵌v0.12保持不變。晚拒絕不能回復前面registry entries副作用，context map零容量／full miss的原null缺口、資源與同步仍為整合前提。

6054F0狀態更新已納入v0.14。[1277920有限查核](roster_mask_reader_findings.zh-TW.md)已固定完整body與兩個roster讀取，mask迴圈未提供已證拒絕結果。下一動作：在原input+10h計時store前定義guard，同時保留普通missing返回，將primary+24h與property+Ch接共同B，完成原指令對照與caller／helper契約；不擴搜無關callee。

## 6. 產生補丁前仍需取得的證據

- **完整存取集合：** 目前找到的是必要位置，仍有尚未收束的大型 global consumer、衍生地址及其他 callee。
- **實際元件需求：** 參考 `player` 清單與目前安裝／執行期資產的等同性仍未確認。
- **其他四人子系統：** host／client 記錄、roster、平台成員、tag73、loadout、tagDA、生成／復活流程仍需與這五個元件共同適配。
- **執行期邊界：** 已定位的 `EXE+1AE380` 尚缺載入後程式；第四次限定擷取仍待授權，本輪沒有執行。
- **多人驗證：** 沒有五位可同時測試的玩家／帳號，也沒有第五人生成、同步、任務生命週期與八人負載結果。

下一個有限離線切點依上節處理完整 `1277920`；departure的真實caller、跨回呼序列化、資源契約與Windows unwind保留為整合缺口，不把v0.12／v0.13有界測試當完整生命週期驗證。平台加入與原生角色建立仍是整體可行性優先缺口。其餘固定陣列、配置／清理、template等同性與rank音效配套仍列在完整範圍內；已收束支線需具體新來源才重開。先前的`72F780`／`730230`仍缺caller的RCX身分，不能列為已完成改接。第四次capture繼續待答覆，不重問、不執行；目前無五位玩家／帳號驗收條件。原生整合及多人實測完成之前，八人Mod的目標保持未完成。
