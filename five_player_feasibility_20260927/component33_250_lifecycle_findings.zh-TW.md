# 元件 33 / 250：固定槽位之外的生命週期與內嵌儲存證據

日期：2026-09-27。範圍：既有 build 25480438 的固定程式擷取，完全離線；未查詢、讀取或修改活程序。

## 結論

這輪補上的證據會改變擴容方案：**33 的 `+0x90` 已有按元件索引讀寫的 byte，不能當作第 5 個指標槽的空白；33 還有第二組 `0x38` byte record；250 的 `0x34` byte record 之外另有 `+0x160`、`+0x164` 兩組 byte 陣列。** 兩物件最後一組已知四槽資料的尾端，都恰好接到 owner 的下一個已發布內嵌物件。

兩者也存在直接使用 owner 固定位移的程式，以及保存原物件指標的登錄表。因此，僅改 append 的 `4`、只搬一組 record、或只改 global 指標，都漏掉了已證實的存取路徑。這些證據尚未形成可用的擴容實作，也沒有證明當前遊戲實際執行了這些 callback。

## 重播與來源

- 腳本：`component33_250_lifecycle_replay.py`。
- 正式結果：`component33_250_lifecycle_evidence_v2.json`，SHA-256 `dfb125ab3edd6b9672eb725981beecb91e1768da9d44b92522e28fd971155280`。
- v2 採納獨立審查：第一版把 250 `[160,164)` 暫列未分類，完整已存 callback 實際已有按 ordinal 的 byte 讀寫，現已修正，並分開描述單向 copy、雙向 swap 與 primary row 清零。舊 `component33_250_lifecycle_evidence.json` 僅保留審計，不作目前布局依據。
- 固定前置結果：`player_component_capacity_evidence.json`，SHA-256 `4dedec98d7759d1f629500c42bb9a70ff611d0e0b73175e36f2c0306c37f8147`。
- 原始 `capture-report.json`：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。
- 原始 `captured-data.bin`：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。
- callback 初始化函式 `[0x556D90,0x55E1E3)` 共 2,127 組 LEA/store；整段 SHA 與 `0x568239` 的直接 call 都有核對。此次從十張表取出 20 個位置，其中 15 個在此初始化函式有賦值。
- 保存 1,883 條所選程式指令。多段函式保留完整 chained unwind fragments；沒有 unwind 的 leaf 由 callback 註冊入口或已驗證的直接 call 證明入口。大型 owner 函式只保存相關視窗，但重播會掃描從函式入口到視窗末端的全部指令，驗證 owner 暫存器沒有中途改值。

重播範例，`--output` 必須是尚不存在的新檔：

```powershell
C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe -B five_player_feasibility_20260927/component33_250_lifecycle_replay.py --evidence C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438 --output five_player_feasibility_20260927/component33_250_lifecycle_recheck.json
```

所有地址都是本次固定 capture 的 game.dll RVA。下列區間均為半開區間，ordinal 是 **component storage index**，未假設等於 network index。

## 1. 十張 callback 表的實際選項

| 表基底 | index 33 | index 250 | 此輪相關用途／直接目標 |
|---|---|---|---|
| `F0B6F0` | `51ABF0` | `543230` | 另一條插入入口，同樣有加一後 `<=4` 的 guard |
| `F0C110` | `51AC70` | `5432B0` | 先前已核對的建立／插入入口 |
| `F0CB30` | `51ADB0` | `5433E0` | 前者 call `6661A0`；後者直接建立 property descriptor 並寫 `+164` byte |
| `F0D550` | `51ADE0` | 未見賦值 | 前者 call `664430`，後續還處理靜態資料 |
| `F0DF70` | `51AE90` | `5434D0` | `ret 0` leaf |
| `F0E990` | `51AD30` | `543360` | 依回傳索引減少 count、視情況搬移既有槽位 |
| `F0F3B0` | `51AEA0 → 666A90` | `5434E0 → 671CA0` | `mov rdx,rcx` 後 tail jump；處理槽位／分段變動 |
| `F0FDD0` | 未見賦值 | 未見賦值 | 不能據此說執行期為 null |
| `F107F0` | `51AEB0 → 666DD0` | `5434F0 → 671F00` | 另一組槽位／分段變動路徑 |
| `F11210` | 未見賦值 | 未見賦值 | 不能據此說執行期為 null |

這裡以程式行為描述 callback，沒有把未證實的引擎名稱當成函式符號。`0x7C` / `0x7F` 是後述登錄資料中的 tag，分別不是 component index 33 / 250。

## 2. 元件 33：`+90` 有既有欄位，並有第二組 record

### 同一個 base 的完整來源

`568230` 在 `568236` 保存 `RBX=entry RCX`。`5683E6` 計算 `owner+3CA0`，`5683ED` 將它寫入 global `33267B8`。下一組 `5683F4/5683FB` 發布 `owner+3F58`。兩個內嵌物件起點相距 `2B8`。

`666DD0` 的完整三段 unwind root 內，`666DEB` 從同一個 global `33267B8` 取得 RBP。entity ID 查表命中後，`666E50` 取 map value 至 EBX，`666E56` 令 ESI=EBX；`666E37/666E3B` 令 `R14D=[base+10]-1`。在非相等索引分支：

```text
666E9E  movzx ecx, byte ptr [r14 + rbp + 90]
666EA9  mov   byte ptr [rsi + rbp + 90], cl
```

這是已註冊 `F107F0[33]` callback 的實際下游，並有明確 global base 與索引来源。故 `+90` 是程式正在使用的索引欄位；尚未賦予它 boolean、玩家狀態或其他語意名稱。在一般有效四槽索引 0..3 下，其 byte 位址為 `[90,94)`；`[94,98)` 仍未分類。

第 5 個指標（ordinal 4）寫 `[70+4*8,70+5*8)=[90,98)`，會覆蓋上述 byte。原先「指標第 5 槽也許只落在空隙」的可能性，已被這條有 base 的程式證據排除。

### 不能只搬 `+98` 這一組資料

`665FE0` 的 ABI 資料流為 `RCX=base, EDX=destination ordinal, R8D=source ordinal`，相同索引直接返回。非相等路徑完整搬移：

| 內容 | 每槽位址 | 實際程式證據 |
|---|---|---|
| entity 指標 | `base+70+i*8` | `666002/66600B` |
| 第一組 record | `base+98+i*50`，80 bytes | `666007..66606E`，五組 16-byte 複製 |
| 第二組 record | `base+1D8+i*38`，56 bytes | `666076..6660BE`，三組 16 bytes 加 8 bytes |
| ID→ordinal map value | `map entry+4` | 搬移後重查 entity ID，`666122` 寫 destination ordinal |

空間的直接算式：

```text
第一組：98 + 4*50 = 1D8    ← 第二組起點
第二組：1D8 + 4*38 = 2B8   ← 下一個內嵌物件相對起點
owner 下一物件：3F58 - 3CA0 = 2B8
```

因此把第一組當成 8 筆會覆寫第二組；保留第二組原起點而擴成 8 筆，會越过下一個物件起點。`6661A0` 也不只生成外部 descriptor：`66634D..66635F` 從已查出的 ordinal 算 `base+1D8+i*38`，直接寫第二組資料。

**搬移規則不能套成一個未经核對的通用 memcpy：** `665FE0` 沒有搬 `+90` byte；`666DD0` 有上述單向 byte 複製，另交換指標與兩組 record、更新 map；`666A90` 亦处理兩組 record。這裡保留原始差異，沒有主張原程式缺陷，也沒有聲稱 `+90` 在每種轉移下都應交換。

## 3. 元件 250：record 後方有兩組獨立 byte 陣列

同一 owner 發布函式 `568230` 中，`568F62/568F69` 將 `owner+EB5178` 寫入 global `33266D0`；`568F70/568F77` 發布下一物件 `owner+EB52E0`，差值 `168`。

`671610` 的參數角色同樣是 base、destination ordinal、source ordinal。`671620/671624` 算 source/destination `i*34`；`671628..67167F` 搬 entity 指標與 52-byte record。緊接著：

```text
671686  movzx eax, byte ptr [r10 + rcx + 164]
67168F  mov   byte ptr [rsi + rcx + 164], al
```

其中 R10D=source、ESI=destination，RCX 仍為同一 base。隨後它也重查搬入 entity 的 ID，於 `6716F2` 將 map value 更新為 destination ordinal。

`F0CB30[250] → 5433E0` 還提供另一條證據：從 global 取 RDI、按 entity ID 查得 EBX=ordinal，`543486` 寫 `byte[base+ordinal+164]=1`，並建立 hash `A3DF1643` 的 descriptor。這支程式只能證明此 byte 和這個 property descriptor 有關；本輪未把 hash 命名為某個遊戲功能。

```text
第一組 record：90 + 4*34 = 160
索引 byte A：[160,164)  （有效四槽索引 0..3）
索引 byte B：[164,168)  （有效四槽索引 0..3）
下一物件：  EB52E0 - EB5178 = 168
```

`+160` 的證據就在已保存的兩個分段 callback 裡：`671DB4/671DBF` 由 `base+source ordinal+160` 單向複製至另一 ordinal；`67208E/672099` 亦是同型讀寫。前者的 RSI 來自 global33266D0，R14/RBP 分別來自 prefix count／map ordinal；後者的 RBP 來自同一 global，R14/RSI 來自 prefix count-1／map ordinal。**`[160,164)` 不是可挪用的未分類空隙。**

第 5 個指標 `[90,98)` 已直接覆寫第一筆 record。第一組 record 的 ordinal 4 從 `160` 開始，也覆蓋兩組 byte 欄位並越過下一物件起點。byte A 若保留起點擴為八項，會覆蓋 byte B；byte B 若保留起點擴為八項，其尾端 `16C` 超出下一物件起點 `168`。

`671CA0` 與 `671F00` 對 `+160` byte 做單向複製；對 `+164` byte 則做完整雙向 swap（`671DF7..671E1A` / `6720D1..6720F4`）。一般搬移 helper `671610` 只搬 `+164`，不搬 `+160`。

primary record 的兩個分類路徑也不能合併成同一種 swap：`671CA0` 增加分類的路徑交換 entity pointers 後，在 `671D78..671D90` 清零選定的 `0x34` byte row；`671F00` 減少分類路徑才交換 primary rows。這些差異都必須保留，不能因為兩者共有指標交換，就把其他欄位都當成交換。

## 4. 初始化、移除及原指標別名

### 內嵌 hash 儲存與登錄

| 項目 | 33 | 250 |
|---|---|---|
| 內嵌 map 儲存起點 | `base+14` | `base+18` |
| map 指標欄位 | `base+58` 指向上述內嵌儲存 | 同左 |
| map bucket count | `base+60 = 8` | 同左 |
| 初始化證據 | `55250A..552578` | leaf `671910..671967` |
| 登錄 tag | `7C` | `7F` |
| 登錄 helper／區段 | `55257A..5525C4` | `B28040..B28112` |
| registry global | `3326E68` | `3326E68` |
| 保存同一物件指標的表起點 | `D18, 1F80` | `48, 1218, 1C78, 1D10, 1D68, 1F98, 5900, 5918` |

33 的 constructor 以 RSI 保存 entry owner，R13 在 `551D3C` 清零且至這段未改；250 的 owner call site 先以 `owner+EB5178` 放進 RCX，call `671910`，緊接 call `B28040`。leaf `671910` 不修改 RCX、不呼叫其他函式，故登錄 helper 收到的是同一個內嵌物件指標。

這同時暴露另一個重定位條件：若複製整個物件到新位址，`+58` 原本是指向舊物件內部的指標，必須另處理；map 的 8 buckets 也不能和 8 個玩家槽位混作同一種容量。本輪未推導新 map 容量或負載率規則。

### 解除登錄仍以原 owner 位址比對

33 的 `55F13C..55F1E7` 明確算 `owner+3CA0`，在上述兩張表按指標比對；命中會減少 count，將末項 16-byte entry 搬來覆蓋移除項。250 的 owner 析構路徑在 `5659B4/5659BB` 以 `owner+EB5178` call leaf `B38710`，該完整 leaf 對上述八張表做同樣的指標比對／末項搬移。

所以替換 global 並不會自動改寫已登錄的物件指標；登錄、使用與解除登錄必須保持同一種物件身分規則。這八／二張表是已證實的別名，沒有聲稱已找齊所有別名。

### 物件內的移除與分段重排也必須涵蓋

`51AD30` / `543360` 從傳入 entity 取 ID，以 `base+58` 呼叫 `172F8A0`，將回傳 EAX 作為 slot index，按 count 與 `entity+14` bit 0 分支，減少 count，並 call／tail jump `665FE0` / `671610`。其 count 欄位分別為 33 的 `+8,+C,+10`，250 的 `+C,+10,+14`；本輪没有替這些不同分段強加完整遊戲語意。

此外 owner 函式 `576CF0` 有兩段直接地址使用：

- `577B16` 算 `owner+3CA0`，`577B3C/577B4D` 直接 call `665FE0`，並更新物件的 `+C/+10`。
- `57E6AC` 算 `owner+EB5178`，`57E6CC/57E6DD` 直接 call `671610`，並更新 `+10/+14`。

這是與 global 讀取分開的一條確定路徑。僅改 global 指向新物件，仍會讓這些 owner 路徑操作原內嵌資料。

## 5. 對擴容方案的具體約束與限度

現在可以確定，需要協調處理的至少包括：兩條插入入口、移除／分段變動 callback、全部並列陣列、ID→ordinal map、內部 map 指標、owner 固定位移存取，以及保存物件指標的登錄和解除登錄。

這支持把下一步實作研究拆成「完整布局與別名重定位設計」及「所有生命週期入口使用同一布局的證明」。尚不能選定簡單 global 替換或僅擴一組陣列的做法。擴大 owner 內嵌區域亦會改變後續成員位移；本輪沒有收集足以完成那種修改的全部 consumer。

本輪不把 reference resource 的 ShipCustomizationComponentData / ShipInventoryComponentData 名稱，提升為已證實的當前 runtime 型別或元件需求。也不由「註冊存在」推論 callback 已被執行。沒有碰到活程序、寫 patch、製作可用 mod，或驗證第 5／第 8 位真人加入成功。
