# `BC2D30`：單一 entity 的 property 格式分派與呼叫來源

後續更新：本頁原先留空身分的末段 `owner+EB5E10 → 799790`，已由[元件 260 容量續查](component260_capacity_findings.zh-TW.md)確認是 reference index260 的同一元件物件。原分派 evidence 保持不變，280-byte 格式與 cursor 算式也不變。

## 範圍與結論

本輪只讀既有、固定 SHA 的捕捉檔。沒有查詢或讀取遊戲程序、沒有新增擷取、沒有修改遊戲；第四次擷取仍未授權。分析收束於 `BC2D30` 的一個格式及元件 41、238、roster 239 的來源鏈；其餘三個接收器只用來核對同一格式的完整長度。

**已確認 `selector = 0x3A7` 會依序套用六段單一 entity 的資料，總 cursor 增量 `0x118`（280）bytes。** roster 段位於 `[0x4,0x24)`，其中 network index 位於整體 payload 的 `+0x10`，由 `60C890` 原樣寫入 `roster + ordinal*0x20 + 0x3B4`。

這個 selector 是引擎 API 寫入本機輸出結構的欄位；目前不能稱它為已解碼的網路封包標頭，也不能把 `0x3A7` 當成玩家序號、元件索引或 reference asset 索引。沒有觀察到玩家執行期確實選用此格式。此分派本身沒有固定四人的迴圈或 `network index < 4` 判斷，但接收器仍使用既有元件的 ordinal 儲存陣列，既有四槽容量限制依然有效。

## 可重播產物

- `property_dispatch_replay.py`：讀固定 capture，驗證引用檔 SHA、unwind 邊界、精確 cursor pins、jump table 和直接呼叫邊。
- `property_dispatch_evidence.json`：正式證據 SHA-256：
  `9cabca2fa61fd59e9c776230da80ad68716f947c46f56c6b9c203ba011d0d55d`。
- `property_dispatch_entry_xrefs.json`：先前完成的 bounded E8/E9 掃描；本次驗證其 SHA 及五條實際呼叫／尾跳指令。
- 11 個完整 unwind roots、754 條 root 指令、94 條選定 span 指令、38 個 cursor pins。
- 捕捉身分：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。
- `captured-data.bin` SHA：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。
- `capture-report.json` SHA：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。

重播命令，輸出檔需尚不存在：

```powershell
& 'C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe' `
  'five_player_feasibility_20260927\property_dispatch_replay.py' `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output 'five_player_feasibility_20260927\property_dispatch_recheck.json'
```

## 1. Payload 與 selector 來自 API 的輸出結構

`BC2D30` 接收 `EDX` 外部 handle，先保存到 `EDI`。此值在已證呼叫端來自 entity record 的 `+0x10`；沒有證據把它直接等同 entity ID 或 network index。

| RVA | 已確認行為 |
|---|---|
| `BC2D3D` | 讀 API global `3326308` |
| `BC2D44`、`BC2D49` | 將 `[RBP-0x10,RBP)` 的 16 bytes 清零 |
| `BC2D4D..75` | `R8B != 0` 呼叫 API `+0x40` 介面的方法 `+0xB0`；否則呼叫 `+0xA8`，都以 `R8=&[RBP-0x10]` 傳入輸出位址 |
| `BC2D63..65` | `+0xB0` 回傳 `AL=0` 則跳 `BC685E` 直接返回 |
| `BC2D85` | `RBX = [global346BFC8]`，既有證據已定位 owner |
| `BC2D81..8E` | `FD9BA0(&[RBP+0x28], handle)` 取得 entity ID |
| `BC2D93` | `EAX = DWORD [RBP-8]`，即輸出結構 `+8` 的 selector |
| `BC2D96` | `RDI = QWORD [RBP-0x10]`，即輸出結構 `+0` 的 payload 指標 |
| `BC2D9A` | `DWORD [RBP+0x20] = 0`，此為後續共用 cursor |

這裡没有從 payload 讀取 selector；兩者都是 API 結果的欄位。輸出結構 `+12` 的意義、API 方法的正式名稱及 API 如何取得資料都未閉合。選定路径沒有使用輸出結構 `+12` 驗證長度。

## 2. `0x3A7` 選定的跳轉表入口

`BC2DA1` 對 selector 作 unsigned `<= 0x73E` 檢查，超出時走 `BC6859` 的返回路徑。通過時：

```text
BC2DAC  RDX = image base
BC2DB3  ECX = DWORD [RDX + selector*4 + BD9EB8]
BC2DBA  RCX += RDX
BC2DBD  JMP RCX
```

捕捉到的 RVA jump table 位於 `BD9EB8`，共有 `0x73F`（1855）個四位元組項目。`table[0x3A7]` 位於 `BDAD54`，bytes 為 `8c 13 bd 00`，解碼目標 `BD138C`。整張表中指向 `[BD138C,BD13FF)` 的項目只有這一項；這不排除其他未分析的間接控制流程。

`0x73E` 是格式選擇值上限，四位元組 table stride 是 RVA 大小；兩者都不是玩家人數限制。

## 3. 六段 payload 與 41／238／239 的接線

各 call 使用相同參數形式：`RCX=owner+offset`、`EDX=[RBP+0x28]` entity ID、`R8=payload`、`R9=&cursor`。接收器更新同一個 32-bit cursor；範圍下界含、上界不含。

| 順序／既有元件對應 | owner 內偏移 | caller → receiver | serialized bytes | payload 範圍 |
|---|---:|---|---:|---|
| 250 | `EB5178` | `BD139D → 671860` | 4 | `[0x0,0x4)` |
| roster 239 | `EA0818` | `BD13B3 → 60C890` | 32 | `[0x4,0x24)` |
| 238 | `E9FC98` | `BD13C9 → 87BB30` | 64 | `[0x24,0x64)` |
| 33 | `3CA0` | `BD13DF → 666590` | 56 | `[0x64,0x9C)` |
| 41 | `4148` | `BD13F5 → 7AF610` | 88 | `[0x9C,0xF4)` |
| 最後一個 member，索引未在本支線證明 | `EB5E10` | `BD1DF2 → 799790` | 36 | `[0xF4,0x118)` |

`BD13FA` 尾跳到共享的 `BD1DE1`，完成最後一段後返回。最後一個 member 只為閉合 280 bytes 而保留；本證據不把它標成已驗的 reference index 260。

### Cursor 與欄位大小的重點

- **250：** `6718EE` 只讀一個 byte、寫入 `S+ordinal+0x164`，但 `6718FB..FE` 將 cursor 加 **4**。因此 roster 起點是 `+4`，不能誤算成 `+1`。
- **239：** `60C890` 共讀八個 DWORD，cursor 加 `0x20`。第四個 DWORD 是此段的 `+0xC`，所以整個 payload 的 network index 偏移是 `4+0xC=0x10`。`60C95C → 60C962` 原樣傳遞 32 bits；沒有 `<4`、clamp 或 mask。
- **238：** `87BBCE..DE` 定位 `S+0xA7C+ordinal*0x40`；16 次 DWORD 的資料量共 `0x40`，最後 `87BC6B..71` 更新 cursor 並寫最後欄位。
- **33：** `66661E..2A` 定位 `S+0x1D8+ordinal*0x38`；cursor 增量 `0x18+8+0x14+4=0x38`。
- **41：** `7AF69E..AA` 定位 **第三個陣列** `S+0x26688+ordinal*0x58`；兩段各 `0x2C`，cursor 共加 `0x58`。不能錯記成先前另一陣列的 `+0x26528`。
- **最後 member：** 動態 backing 指標 `[S+0x50]`，record stride `0x24`；包含一個只讀 byte 卻佔四位元組 cursor 槽位的欄位，總增量仍是 `0x24`。

這些大小描述單一 entity 的欄位格式，沒有四名 entity 的內嵌批次。cursor 使用 DWORD，程式算術會按 32 bits 回繞；上述範圍以本分派從零開始且完整返回為前提。

## 4. 直接 caller 與 reference component-index 清單

bounded E8/E9 掃描加 unwind 邊界驗證，找到四條 `call` 和一條尾跳：

| caller root | 指令 RVA | `R8B` | 本次已閉合範圍 |
|---|---|---:|---|
| `581C40` | `581DA9` | 0 | 完整 root；前後各迭代元件清單並呼叫 callback |
| `FDBB40` | `FDBE10` | 0 | 選定 callback 迴圈尾端、API 取得 context 及 apply 區段 |
| `FDC140` | `FDC29B` | 1 | 完整 root；建立 entity 後依序加入元件、插 map、apply、post callback |
| `FDDE30` | `FDDE6A` | 1 | 完整 root；從 `self+0x1C` 的 DWORD handle 陣列遍歷 `self+0x18` 計數 |
| `FDDE90` | `FDDEB3`，`jmp` | 1 | 完整 root；單一 handle 包裝器 |

這是已捕捉、unwind 覆蓋的直接邊，不能排除間接 caller 或無 unwind leaf 中的其他邊。

`581C40` 明確使用 resource metadata 的 component-index 清單：

1. `581D1D..37` 經 context 的 `F12EA8`／`F12EA0` 取清單指標及數量。
2. `581D60` 讀 uint16 component index，`581D63` 查 owner 的 `F0F3B0[index]`，非空時呼叫。
3. `581DA9` 呼叫 `BC2D30`。
4. `581DC0..DA` 再以同一份 uint16 清單查 `F0FDD0[index]`。

**清單驅動的是 apply 前後的 callback；本次選定的 apply 內部分支由 API 的 32-bit selector 決定。** 本證據沒有把 reference player 九元件清單、selector `0x3A7` 及實際 installed/runtime 玩家選擇強行視為相同身分。

## 5. Handle → entity ID 不構成完整的有效性保證

`FD9BA0` 使用 `[global346BF98]` context 的 map `+0xF22EC8` 查外部 handle，從 map value 取得 entity record ordinal。record 位於 `context+0xF32F18+ordinal*0x18`；函式讀 record `+8` 的 entity ID，寫入 caller 的 `[RBP+0x28]`。

- `handle==0x7FFF` 直接回傳 `[global348456C]` sentinel。
- 一般查找失敗可能回傳同一 sentinel；map 走到「無 entry」路徑時會把指標清零，後續 `FD9C44` 仍解參考，因此不能把函式描述為安全的 not-found lookup。
- `BC2D30` 在呼叫接收器前沒有再驗證此 entity ID。`60C890` 的無 ID 路徑也沒有安全拒絕，會使用 ordinal `0xFFFFFFFF`；其完整證據由 `roster_property_receive_evidence.json` 提供。

`FDC140` 可證明一條有用的建立順序：`FDC25A → 581320` 加入元件，若 handle 不為 `0x7FFF`，`FDC275 → 172F790` 插入 handle map；只有此 handle 條件通過且 creation parameter 第一個 byte 為 0，才在 `FDC29B` 執行 apply，之後 `FDC2B1 → 581780`。此順序支持該建立路徑的前置條件，但不能單憑它保證所有 caller 都有有效 ID、正確 component membership 或足夠長的 payload。

## 6. 對八槽改造的具體意義

| 項目 | 本輪結論 |
|---|---|
| 將這條分派的四人數量改八 | 沒有找到這種數量常數；不應修改 table stride 4 或 selector 上限 `73E` |
| 單一 entity 的 property 格式 | 已確認各段固定欄位長度，沒有四名玩家的內嵌陣列；可作為「保留每 entity 格式」設計的依據 |
| 41／238／239 的目的地容量 | receiver 以 entity-map ordinal 索引，仍會遇到既有四槽結構；必須沿既有 lifecycle 結果擴容 |
| 元件搬到新 owner 位置 | `BD13A5`、`BD13BB`、`BD13E7` 是直接 owner 偏移別名，必须同步重接；只改 global 不足 |
| Network index 4–7 的傳值 | 這個 reader 原樣接收 DWORD，局部沒有拒絕或截斷；不代表其他 index consumers、sender 或平台已支援 |
| 仍未證明 | API 如何產生 payload／selector、傳輸 framing／長度保證、實際 player 是否選 `3A7`、第 5–8 人能否抵達此路徑 |

本輪將「資料格式固定四人」排除為此選定分支的直接證據結論；尚未排除引擎 API、其他 schema 或平台限制。沒有建立可用八人 mod，也沒有做第五人加入測試。
