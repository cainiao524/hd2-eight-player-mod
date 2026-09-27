# 同一 D 的四筆 float records：有限 consumer 集合與八槽改接清單

後續補證已確認[外部q來源](indexed_float_external_index_findings.zh-TW.md)、[子物件與共用池](indexed_float_subobjects_findings.zh-TW.md)、[rank ID的Wwise用途](indexed_float_rank_ids_findings.zh-TW.md)，並核對[兩個下游helper](indexed_float_helper_boundaries_findings.zh-TW.md)。本頁及原JSON保留當時有限consumer集合，相關未知項的最新狀態以上述續篇與總設計稿為準。

## 範圍與結論

本輪只延伸已證明的 `D+80E18` 陣列及其 manager 呼叫路徑。**可以確認：把 `14335F0` 的 writer 改到八筆新記憶體，仍不足以完成這條子系統的八槽支援。** 同一 D 還有初始化、清理、固定四筆更新／讀寫、每次處理兩筆的展開迴圈、兩張四格 metadata 表，以及四格 stack 索引表。另有三張只初始化三個 ID 的表，對應非本機條目的 rank。

這是具有 D 基底身分證據的有限清單，足以改變下一步擴容設計；不是所有 consumer 的完整清查。沒有讀取活程序、啟動遊戲、修改記憶體、製作可載入 patch 或測試八人連線。

## 固定來源與重放

- 前置 D 身分／儲存區證據：`indexed_float_storage_evidence.json`，SHA-256 `11e984e270540eded0e141f821ddfbb22118c0b99645237eca15e14149d42378`。
- 本輪正式證據：`indexed_float_consumers_evidence.json`（schema v2），SHA-256 **`503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578`**。
- 重放程式：`indexed_float_consumers_replay.py`。共保存 **5,231 個 instruction rows**，涵蓋 12 個選定 root 的正常程式範圍、manager 的兩段呼叫視窗及兩個保存／還原 pins，另保存基底前綴的 hash／所有明確 register writes、semantic pins、正常 CFG reaching definitions。
- 另外釘住獨立 caller CFG 證據 `indexed_float_consumers_review_caller_cfg.json`，SHA-256 `b1ac8e336b754ee5ec7cc55128ddb3b5670eaf11f9419c38843a5b472cd5ef90`。它核對完整 caller 的 5,507 個 instructions；這些不重複計入上述 5,231。主 replay 驗其 SHA 與補充的保存／還原 pins，沒有聲稱在主 replay 中重算該獨立 caller CFG。
- 固定 capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。重放會先驗證原始 report/data SHA、前置 JSON SHA 與相同 capture 身分，再逐指令核對 saved bytes 和 unwind 邊界。
- `142CB90` 正常 epilogue 在 `142D830 ret` 結束；`142D831..142D834` 為三 byte NOP，接著 `142D834..142D864` 是有實際 dispatch 引用的 12 個 DWORD RVA。`142CE90` 令 EAX 減 C，`142CE93/96` 排除超過 B 的 unsigned index；`142CE98` 讀表、`142CEA0` 加 image base、`142CEA3` 間接跳轉。四個唯一 target 都是已確認 instruction 邊界。
- v2 明確處理該 dispatch 後，`142CB90` 正常 CFG 可達 673 個已保存 instructions。R13 中途亦被重用，故以 CFG 核對 dispatch 的 reaching definitions 只來自 `142CC4D/142D1B8`，兩者都是 image-base LEA。尾端 table bytes 以資料保存，不當成 instructions。

可重放至**不存在的新檔名**：

```powershell
& 'C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe' -B `
  five_player_feasibility_20260927/indexed_float_consumers_replay.py `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output five_player_feasibility_20260927/indexed_float_consumers_recheck.json
```

## 1. 同一物件的來源與呼叫鏈

沿用已驗證的符號：`M` 是 manager，`k` 是其 instance ordinal，`n` 是 roster network index。

```text
M = global3326AA0 = owner+1F7AE8
U = M+4F90+k*55A698
D = U+4C8260 = M+k*55A698+4CD1F0
```

`k` 與 `n` 不混用。前置證據已接上 initializer `724542→142B990`、writer `7275FA→14335F0`、cleanup `724DF6→142C9B0`。

本輪在完整 `725160..72AD3D` 前綴核對 RSI 的所有明確改寫。最後兩次是 `727516 lea RSI,[R14+4F90]` 與 `727537 add RSI,RAX`；到以下呼叫時，RSI 仍是相同 U。每列均有 `RCX=RSI+4C8260` 的實際 address formation：

獨立完整 caller CFG 另核實迴圈回邊：六個 D address formation 的 RSI reaching definition 都只有 `727537`。`727516` 的 R14 可以來自入口 `7251A4` 或回邊 `72B230`；後者從 `[RBP+130]` 還原，而 `7251A7` 保存 entry RCX=M。包含正常 frame 中 RBP/RSP 別名與寫入寬度的核對顯示，該槽唯一寫入是 `7251A7`。因此對後续迭代的 M 身分不是靠「前綴未改 R14」作推論。

| 呼叫位置 | 目的 root | 本輪意義 |
|---|---|---|
| `727579` | `14329B0` | 兩筆展開的 float 讀寫 |
| `7275FA` | `14335F0` | 原先的 network-index writer |
| `72AC70` | `142C9B0` | 相同 D 的清理 |
| `72ACC6` | `142BED0` | 狀態及 metadata 表初始化 |
| `72AD11` | `142D870` | 兩組四筆迴圈、索引路徑及 stack map |
| `72AD38` | `1430450` | 四筆 record／子物件處理與索引讀者 |

這些呼叫有既有分支條件，不能解讀成每一 tick 全部無條件執行。

在 D 方法內另外接上：

- `142D8B9→142EE70`：RCX 保留 entry D；`142D975→142CB90`：RCX=RSI=D。
- `14335F0` 的 `14336FC/1433710→142FF90`、`1433706→1433020`：RCX=R14=D，EDX 保留輸入 n。
- `142D870` 的 `142EA85/142EA90→1433020/142FF90`：RCX=還原後的 R14=D；EDX 為 `606820` 回傳的 roster index。
- `142CB90` 的 `142D7EB→142FF90`：RCX=RDI=D，EDX 是迴圈 slot。
- `142FF90` 的 `14303AB/14303DD→142FED0`：RCX=RSI=D。

### 防止把 register 重用誤判成同一基底

`142D870` 中途會把 R14 改成整數 ordinal／offset；本輪沒有假設它全程不變。完整正常 CFG 的 reaching definitions 顯示：在 `142EA70` 的索引存取、以及 `142EBA1` 第二迴圈取基底之前，R14 的來源只能是 `142DF98 / 142E2D4 / 142E5B4 / 142E7D7` 四個 `mov R14,[RSP+68]`。該保存槽唯一寫入是 `142D8A7 [RSP+68]=entryRCX`。

同樣，`142EB0B` 用來初始化 rank 的 R12D，CFG 可達定義只有五個 `xor R12D,R12D`；因此不是拿未確認的 register 值當作 0。這些結論以正常控制流及 Windows x64 nonvolatile register 保存慣例為前提，不描述 exception unwind 的執行路徑。

## 2. 已接上 D 的 record consumers

固定 layout 是四筆 `[D+80E18,D+81878)`，每筆 `298` bytes。五個內嵌 `78`-byte 子物件起點為 record-relative `+28/+A0/+118/+1A0/+218`。

| Root | 已證 record 讀写／用途 | 現有筆數或 gate |
|---|---|---|
| `142B990` | 每筆清零 `298`，初始化五個子物件 | `142BB94` count=4；`142BC2C` stride=`298` |
| `142C9B0` | 對同五個子物件呼叫 `140C200` 清理 | 四筆、stride=`298` |
| `14329B0` | 讀改寫 `record+C` 的兩個 float | **每次兩筆、兩次迭代，共四筆** |
| `142CB90` | 從 record flag 掃描 enabled records，呼叫 `142FF90` | `142D7FA` 比較 4 |
| `142D870` 第一迴圈 | flag 與五個子物件的狀態／方法呼叫 | `142DF8E` 比較 4 |
| `142D870` 第二迴圈 | 讀 `+4/+C/+14` float pairs，寫回 `+4/+14`，讀取 stack map／ID tables | `142EDC6` 比較 4 |
| `1430450` | flag、`+14` float pair、`+24` float 及子物件欄位 | `1430DE3` 比較 4；metadata pointer 同時每次加 4 |
| `14335F0` | `D+n*298+80E24` qword store、flag 與下游呼叫 | 首次 store 前沒有數值 `<4` gate |
| `1433020` | 相同索引位置的兩 float 讀改寫 | 座標數值 clamp 不是 index 容量檢查 |
| `142FF90` | 索引 float、metadata，以及 record `+28/+A0` 子物件 | 輸入 n 必須等於 `606820` 選定的 local/current index，否則先返回 |
| `142FED0` | enabled flag 掃描，並讀寫 per-index metadata | `142FF2B` 比較 4 |
| `142EE70` | `D+q*298+80E24/+80E28` float 讀者 | q=-1 時跳過；q 的外部表語義／上游範圍尚未閉合 |

### 不能只搜尋 `cmp 4` 的例子

`14329B0` 令 RBX=`D+810BC`，也就是第二筆的 float pair；同一迭代同時操作 `[RBX-298]` 與 `[RBX]`。`1432A00` 設 ESI=2，`1432E8B` 每次 RBX 加 `530=2*298`。因此它是四筆的兩兩展開。寫回依分支發生：第一對的 qword writers 是 `1432BCE/1432C8F`，第二對為 `1432DCA/1432E80`，不代表每輪無條件覆寫。八筆等價遍歷至少需要四次雙筆迭代，並同步改接 record address formation。

### 個別索引路徑的條件

`142D870` 的動態索引來自 `606820`，在 `142EA69` 乘 `298`。在存取前可見 entity sentinel、index=-1、record enabled 等條件；這些條件不是 `<4` 保護。

`1430450` 在 `1431506` 讀相同 roster global `3326468`。若 roster+88 非零，`1431523` 直接取第一筆 roster 的 +3B4 network index；否則給 -1。`1431646` 與 `1431A6B` 以它乘 `298`，讀同 D 的 `+80E2C/+80E30`。這裡只將來源命名為第一筆 roster network index，不擴張為所有執行狀態下的固定本機 ID。

`142EE70` 雖已證 D，索引 q 來自另一 global 的 `+16398`、stride `20` 表：先匹配 `+B3A8` 指標，再從匹配 entry 的 `+14`（表基底相對 `+163AC`）讀 DWORD。它有 -1 檢查；本輪沒有把 q 直接等同 roster n。

## 3. 兩張 metadata 表亦只有四格

同 D 的 `142BED0` 初始化兩張相鄰 DWORD 表：

| 範圍 | 初始化 | 已確認 consumer |
|---|---|---|
| `[D+8D6C4,D+8D6D4)` | 兩個 qword 設為 all-ones，相當四個 -1 DWORD | `142FF90`、`142FED0` |
| `[D+8D6D4,D+8D6E4)` | 兩個 qword 清零 | `142FF90`、`142FED0`、`1430450` |

`142C867/142C879` 寫第一表，`142C872/142C884` 寫第二表；RCX 在 `142BFAC` 清零。`142FED0` 同時以 record stride `298` 和 metadata stride 4 遍歷四筆。

第一表原地加到 index 4 就開始覆蓋第二表。第二表 index 4 起點是 `D+8D6E4`，而 `142BEF9` 已在此寫入 qword 狀態；另有 `+8D6EC/+8D6F0` 的實際寫入。因此兩表不能只各把初始化次數改成 8 後原地使用。它們各需四個額外 DWORD，亦須改接已證讀寫點；這 32 bytes 只是新增邏輯元素總量，不是整體配置／對齊成本。

## 4. Stack map 第 5 格覆蓋已使用的 ID

`142D870` 在 `142EB0E/142EB16` 用兩個 all-ones qword 初始化 `[RBP-60,RBP-50)`，正好四個 DWORD。接著以 roster+84 為枚舉筆數、從 roster+3B4 起每次前進 `20` bytes 讀 network index n。只跳过 n 等於目前選定 local/current index 的條目，其餘執行：

```text
142EB77 ECX = rank
142EB7A rank++
142EB7D [RBP+n*4-60] = ECX
```

**若走到這段且 n=4 未被 local/current 條件跳過，目的位址就是 RBP-50。** 此欄位不是未分類 padding：`142EB33` 剛把它初始化為 `56D7E815`，稍後 `142ED3B` 會把它當作 rank-indexed ID table 的第一個 ID 讀入 EDI。

所以即使後面的 record 遍歷仍然只跑四筆，這張 stack map 在枚舉到非本機 index 4 時就有具體 overwrite。此結論是條件式位址／資料流證明，沒有宣稱目前遊戲已執行這次覆寫或已有某種 crash 表現。

## 5. 非本機 rank 的三張 ID 表

`142EB1E..142EB56` 分別初始化下列三張表，每張只有三個 DWORD：

| Stack 基底 | 現有三個值 | 使用點 |
|---|---|---|
| `RBP-70` | `2E1387C5 / ED9E2BBD / 30E087B2` | `142ED37` |
| `RBP-50` | `56D7E815 / CE12B5A6 / D2D33C0C` | `142ED3B` |
| `RBP-80` | `25065DD3 / 6E61441F / 833E051C` | `142ED3F` |

表索引是 stack map 讀出的非本機 rank；它有 -1 sentinel 檢查，沒有再把 rank 限在 0..2。ID 後續傳給 lookup／其他呼叫；本輪不把它们命名為顏色、UI icon、音效或其他未證明資源。

**只有在八筆 roster 中確實包含有效的 selected local/current index 時，未被跳過的 rank 才最多七項。** 實作需為此情況提供七個有效 ID 或有明確界限的 fallback。原程式允許 `142EA4E` 將 selected index 設為 -1；若八筆有效 n 都是 0..7，就沒有任何一筆因 n==-1 而跳過，rank 可達 7、共八項。因此需先驗證／拒絕缺 local 的狀態或為它提供受界限保護的 fallback，不能把七格當成無條件安全容量。現有資料不足以直接填入新資源 ID。

## 6. 有限且具體的八槽改接清單

1. **配置八筆 record 並建立完整生命週期。** 八筆共 `14C0` bytes，較原四筆多 `A60` bytes。原地擴張會碰到前置證據已確認的相鄰已初始化物件，必須規劃搬移或重新布局。每筆的五個子物件及 owner/pool 指標關係亦須保留。
2. **改接本稿已列出的 D-relative field 與 interior-object address formation。** 包含 n/q 索引路徑、線性掃描、`14329B0` 雙筆展開。generic helper 收到的是子物件指標，不能把呼叫邊界簡化成所有 helper 都直接知道 D。
3. **同步更改已證固定筆數。** 初始化、清理、`142CB90`、`142D870` 兩迴圈、`1430450`、`142FED0` 的四筆界限；`14329B0` 的兩次雙筆迭代改為四次。
4. **搬移／擴大兩張 per-index metadata 表。** 連同初始化及 `142FF90/142FED0/1430450` 已證讀寫點處理，避免侵入下一成員。
5. **重新布局 `142D870` stack map。** 同時處理 stack frame、unwind、呼叫對齊和每個 network index 的合法性；只改 store offset 或擴大 loop 都不能代替這些條件。
6. **處理三組 rank-indexed ID 的容量與 local 選取前提。** 八筆中包含有效 local 時需七個有效選項或 bounded fallback；缺 local／invalid local 時需驗證、拒絕或安全 fallback，因為可能枚舉到八個未跳過的 rank。不能假設第 4 個以上的現成資源已存在。
7. **在製作 patch 前關閉下列未完成邊界。** 本清單是必要改接項，不構成已可安全實作／可運行八人的充分證明。

## 7. 未閉合清單與限制

- 尚未完整枚舉所有 manager callsites、所有 D 別名、外部 callsites 和 runtime lifetime。`1433380/142F860` 等相同 offset 候選未因相似字面值就列為同一 D。
- `142EE70` 的外部索引 q 語義與上游範圍仍未閉合。
- `140C2E0/140C630/140C6A0/140D710/142F6E0` 等 interior-object helpers，以及 `142FA60/1432F10` 等被呼叫方法，在此是保存可見呼叫邊界，並非完整 relocation 審查。原有 backpointer `+8=D`、pool pointer `+20=D+36F8` 要求搬移方案維持實際關係，不能直接假設 memcpy 即可。
- 三張 ID 表的資源定義、更多選項及 fallback 的產品意義仍需後續證據。
- D 的精確類別／UI 名稱仍不明；同一 parent 的 `Galaxy_map_3d` 字串不構成 D 的直接命名證據。
- 尾段 `142D831..142D864` 的 NOP／referenced RVA table 已另存；正常 CFG 使用其四個 instruction targets，沒有把 table bytes 本身當作程式。
- 所有大小、碰撞及必要改接判斷都是固定保存版本的離線證據。不能據此聲稱八人可加入、平台接受索引、遊戲已成功生成八人或此份清單覆蓋全部修補點。
