# P5 原生整合邊界：已知呼叫時點與未證明的排他條件

## 實作決定

**現有保存證據足以定位同一 D 的建立、更新及清理呼叫，尚不足以實作可啟用的 `snapshot → preflight → native executor` adapter。** 現有 Lua 地址清單、bytes 驗證與容量規劃保留為離線元件；不得加入由呼叫者手填 `sync=true` 等旗標便啟用原生操作的路徑。

本項推進八人資料生命週期及穩定性要求。這輪的停止條件是釐清：哪些位置只證明正常呼叫順序、哪些條件仍需具體的引擎整合證據。已達此有限停止條件；不繼續泛查所有 callees 或將更多合成模型當成引擎排他證明。

## 可用但有限的時點

沿用已核對的基底身分：`D=M+k*55A698h+4CD1F0h`；k 是 manager instance ordinal，不是玩家 network index。

| 已證位置 | 可用資訊 | 不能據此推出 |
|---|---|---|
| `724542 → 142B990` | 同一 D 的 constructor 入口；建立 pool 與原 305 個直接 S | D 在其他執行緒不可見、唯一初始化、sidecar 已配置 |
| `724DF6 → 142C9B0` | 另一條已接合 D 的 cleanup 入口 | 所有析構／reset 路徑只由此進入 |
| `72AC64 → 142C8A0`，正常返回後 `72AC70 → 142C9B0` | manager 的一條分支先呼叫該 helper，再清理 D 的 S；之後跳過此區更新段 | 前一 helper 是鎖、全引擎資源已停止使用、沒有回呼 |
| `72ACC6 → 142BED0` | 該分支需要初始化／重設時的已證 D 呼叫 | 清 counter 等同釋放 nodes，或此處可重新清 active pool |
| `72AD11 → 142D870`，正常返回後 `72AD38 → 1430450` | 同一 invocation 內的更新／後續處理順序；D address formation 已證 | 執行緒歸屬、鎖持有、跨執行緒排他或 native callback 不重入 |
| `142D975 → 142CB90` | cache flag 條件下的 builder 呼叫 | flag 是 mutex、交易編號或一致性 token |

`72AD11` 返回後、`72AD38` 之前只能觀察**已經發生的配置**。將驗證放在此處不能稱為對 `142D870` 內配置的 preflight 保護；後驗失敗也不能撤銷已完成的外部資源操作。

若在 `72AD11` 之前規劃，仍缺本輪實際 operation 的來源：各條件、動態模板、原生呼叫順序，以及 callees 的狀態變更是否會影響其後分支。手填 operation 表得到 `fits`，不能推導原函式將執行相同操作或可安全繼續。

## 本輪有限同步檢查

重新讀取 pinned capture 的完整 manager `[725160,72B8E0)`（5,507 條指令），並核對既有 subobjects、lifecycle、counter evidence 中保存的 code spans。限定檢查這些本地指令是否直接含 `lock`、memory `xchg`、`cmpxchg`、`xadd`、fence 或 `pause` 同步候選；本範圍沒有找到。

**這不是無鎖或單執行緒證明。** 同步可能在未解析的直接／間接 callee、外層 scheduler 或其他路徑。沒有把 opaque callee 假定成已知的鎖，也沒有擴大成整個程式的同步掃描。

目前可使用的機制是版本固定的 call／return 邊界、已證 D 的參數傳遞及直接生命週期清單。正常 Windows x64 nonvolatile register 保存可支援此參數身分推導，不能提供排他或物件存活保證。

`D+80D9C` 的狀態 byte、`D+8D709` 的 cache byte、P occupancy／used count 都沒有在此證據中取得排他語義。兩次讀到相同 bytes 也不能排除兩讀之間的修改或先改後復原。

## 原生提交前確定仍缺的條件

1. **有實際根據的同步機制。** 須指明引擎執行緒／scheduler phase 或具名鎖的契約，且涵蓋讀取、規劃、整批 native 操作與必要後驗期間，連同同一 D／P 的其他讀寫及 cleanup 路徑。Mod 自有 mutex 不會自動約束未使用該 mutex 的原生程式。
2. **回呼與重入契約。** `C2E0` 配置及 `C200/1408F00` 清理會呼叫外部資源 helper／API。現在沒有證明這些呼叫不會重入、修改同一 pool 或觸發 context teardown。只禁止 adapter 自己遞迴，不能排除其他原生入口。
3. **本次操作計畫與實際執行一致。** 須接合真正的 S／template 來源、條件及順序；將 opaque 影響列為不可執行的缺口，而不是假定它們與手填計畫一致。
4. **物件存活及搬移提交。** D、P、templates、外部 context、sidecar 與 pool backing 在整批操作期間必須有效；原有 aliases、舊 S 停用與清理路徑須共同改接。地址、版本或 bytes 一致不證明 allocation generation 相同。
5. **有資源語義的失敗恢復。** C2E0 可能部分配置並先記 requested ID；同 ID 不自動補齊。C200 會呼叫外部清理，再更新 occupancy／used count。還原舊 bytes 不能復活已釋放的 handles 或撤銷外部副作用；目前沒有可啟用的恢復契約。

這些條件未滿足時，離線元件保持 `executable=false`。本輪不產生假裝具備同步保護的 native executor，也不擴張任何先前的單次唯讀授權。

## 下一個有效動作

P5 的已知地址規格、資料驗證及保留占用規則已可供未來 adapter 使用。現在應推進其他仍可離線閉合的必要工作，例如 P3 原生資料存取及生命週期改接清單。只有取得**具體新證據**（已識別的原生 scheduling／鎖契約、callback 及生命週期來源，或另行授權取得的相關執行證據）才重開本項同步判斷；更多同型合成測試不會消除此缺口。

## 固定來源與檢查界限

| 保存證據 | SHA-256 |
|---|---|
| `indexed_float_consumers_evidence.json` | `503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578` |
| `indexed_float_consumers_review_caller_cfg.json` | `b1ac8e336b754ee5ec7cc55128ddb3b5670eaf11f9419c38843a5b472cd5ef90` |
| `indexed_float_subobjects_evidence.json` | `5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54` |
| `indexed_float_pool_lifecycle_inventory_evidence.json` | `7722b443b293e565b1600fccbbb8820c0ef01e281f86aac237abb1419e20fda6` |
| `indexed_float_pool_counter_bounds_evidence.json` | `aae3906ab3672a3b0f8ed631fdfddeec11bb7b636e3b5bfbb7083d3554f048d4` |

另核完整 manager bytes SHA-256：`6453c299b8e034bc521478e71a2e9144d1ea2afcd65c080f96244dce84ea725b`。來源仍是既有 capture identity `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`；report／data 由既有 Image reader 的固定 SHA gate 驗證。

這是有限的整合邊界評估，沒有修改既有源碼或正式 evidence、讀取遊戲程序、執行 native code、安裝 Mod 或測試多人。call 順序與靜態指令核對不能代替引擎同步或八人驗收。
