# 元件 41：四組連續儲存、名冊搬移與直接 owner 別名

## 本次閉合的設計問題

**元件 41 不是只有一組大記錄加一組小記錄。** 固定程式證明它有 entity 指標、大記錄及兩組 `0x58` bytes 記錄；最後一組尾端恰好是下一個獨立子物件的起點。除了全域指標，外層 owner、`tag 0x80` registry、更新、整合待處理記錄、屬性套用及取消登錄均保存／形成同一物件的直接別名。

這改變八槽重新配置的範圍：**只修改 `global 0x3326998`、只擴第一組小記錄，或只改加入護欄，都會漏掉已證明的存取。** 已固定實際 callback、初始化、單向壓實、前段移入／移出、屬性產生／套用、更新合併及 registry 清理；沒有宣稱已列完遊戲內所有 consumers。

本頁稱它「元件 41 儲存物件 S」。`ShipModulesSyncComponentData` 僅為參考 FileDiver 資產的 data type 名稱，沒有據此猜 native manager 的正式類名。參考 player 清單與現行 installed／runtime metadata 等價性仍未證明。

## 1. 固定來源與重播結果

正式產物：

- `component41_lifecycle_replay.py`。
- **`component41_lifecycle_evidence_v2.json`**，SHA256：`0f902df704cffb16992d483e099867f5e05708e6d32bdf1672128eca744721df`。
- 初版 `component41_lifecycle_evidence.json` 保留；v2 補入完整 post-setup helper 及外層 owner callers，應以 v2 為準。

重播從原捕捉重新核對 `player_component_capacity_evidence.json`（SHA256 `4dedec98d7759d1f629500c42bb9a70ff611d0e0b73175e36f2c0306c37f8147`）元件 41 的全部指令。正式證據含 **14 個完整 unwind roots／1,260 條指令、3 個有獨立入口證明的 leaf／112 條指令、305 筆選定指令**。

原來源固定為：

- `capture-report.json`：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。
- `captured-data.bin`：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。
- capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。

全部位址是固定 game.dll 的 RVA。本次沒有 live/query/capture、修改遊戲、安裝 Mod 或多人測試，也沒有修改總報告。

## 2. 外層 owner、真實下一個成員與 tag

### 同一 owner 的來源已連接

```text
FDA352: RCX = 原 context + 0x40
FDA360: global346BFC8 = RCX
FDA375: call 551B60
  551B7A: RSI = RCX              ; component owner O
  551B7D: call 568230
    568236: RBX = RCX
    568242: global3326540 = RBX  ; 同一 O
    568448: RAX = O + 0x4148
    56844F: global3326998 = RAX  ; S
    568456: RAX = O + 0x2A930
    56845D: global3326BD0 = RAX  ; 下一個子物件
```

最後一個全域精確 RVA 為 **`0x3326BD0`**。本頁不以全域符號相似推定身分：上述 LEA/store 都保留原 bytes 與 unwind 邊界。

Constructor 接著在 `0x5527FE..0x55285B` 對 `O+0x2A930` 的 counts、embedded hash entries 和 header 做獨立初始化；`0x5715BE` 又將該地址傳給不同更新 helper。因此 `O+0x2A930` 是有實際初始化與使用的下一成員，不是憑最後一條已見存取猜出的界線。

```text
S = O + 0x4148
next = O + 0x2A930
next - S = 0x267E8
```

這是外層 owner 內相鄰成員的 span，沒有將它冒稱為獨立 heap allocation 的大小。

### Tag 0x80 與取消登錄

`0x552717` 形成 S，`0x552776` 將 S 保存到登錄記錄，`0x55277A` 放入 tag `0x80`，再將同一 16 bytes `{pointer,tag,...}` 複製到 global `0x3326E68` 下五個 registry：

| registry count | registry entries | 登錄 store |
| --- | --- | --- |
| `+0x1210` | `+0x1218` | `0x55278E` |
| `+0x1FD8` | `+0x1FE0` | `0x5527AB` |
| `+0x2000` | `+0x2008` | `0x5527BE` |
| `+0x2048` | `+0x2050` | `0x5527DB` |
| `+0x5928` | `+0x5930` | `0x5527F4` |

外層清理 `0x55F3A8/0x55F3AF` 直接以 `O+0x4148` 呼叫 `0xB389B0`。這個無 unwind leaf 由直接 call 證明入口，完整分析至 `0xB38B4E` exclusive（含兩個 return），逐一在上述五張 registry 比較 pointer、找到後以最後一筆 16 bytes 覆蓋並減少 count。它沒有釋放這塊 embedded S 的 heap block。

若改採外部儲存，registry 中的 pointer 副本、清理查找所用 pointer 與各直接 owner 別名都需要一致；只換全域不會自動更新它們。

## 3. 精確布局：第三組記錄補上了尾端

令 i 為 **元件自身的 entity-ID→ordinal 映射結果**，不能視為 network index。

| S 相對位置 | 內容／長度 | 原生尾端 exclusive |
| --- | --- | --- |
| `+0x0` | 已觀察到更新為 `max(old,+8)` 的統計值 | `+0x4` |
| `+0x4/+0x8/+0xC` | 總數、已整合前段數量、bit0 分類前段邊界 | `+0x10` |
| `+0x10` | 8 個 embedded ID→ordinal hash buckets，每個 8 bytes | `+0x50` |
| `+0x50` | hash header；pointer、capacity、invalid key、乘數等 | 指標陣列前 |
| `+0x68 + i*8` | 4 個 entity pointers | `+0x88` |
| `+0x88 + i*0x9928` | 4 個大記錄 | `+0x26528` |
| `+0x26528 + i*0x58` | 4 個記錄，更新路徑中的既有／已套用內容 | `+0x26688` |
| **`+0x26688 + i*0x58`** | **4 個新增確認記錄，屬性產生／接收內容** | **`+0x267E8`** |

三個等式由保存程式中的基底／步幅直接算得：

```text
0x88    + 4*0x9928 = 0x26528
0x26528 + 4*0x58   = 0x26688
0x26688 + 4*0x58   = 0x267E8 = next-S
```

因此第四索引開始：pointer 會覆蓋大記錄 0，大記錄會覆蓋第一組小記錄，第一組小記錄會覆蓋第二組小記錄，**第二組小記錄會跨入下一個子物件**。

若保留每筆資料尺寸、hash/header 的原長度，從四筆到八筆的四組資料增加量為 `4*(8+0x9928+0x58+0x58) = 0x26780` bytes；整段至少由 `0x267E8` 變成 `0x4CF68`，未包含可能額外的 alignment／其他設計需求。這是尺寸計算，不是可直接套用的新布局。

### Hash table 容量應分開處理

`0x552703` 清零 `S+4/+8`；`0x55270A/0x55271E` 將 `S+0x50` 指向 embedded `S+0x10`；`0x552728` 設 capacity 8，`0x552738` 設乘數 2。迴圈逐一清零 value 並填入 invalid key。R13D 的零值來源是 `0x551D3C`。

完整 `0x172F790` insertion 最多 probe capacity 次：找到 invalid／同 key 時寫入 ID 和 ordinal；找不到時以空指標寫入，沒有自動增容。完整 `0x172F8A0` deletion 先找 key，標 invalid，再進行**最多 capacity−1 次**的後移修復（backshift）。

這裡的 **8 buckets 不是八位玩家已支援的證據**；但它確實能在表示層容納八個 distinct keys，保存實作也沒有另一個 `<4` 或 half-full 插入條件。不能無證要求一定改成 16 buckets。若保留 8，仍需驗證全滿表的加入／移除與其他不變條件；本次未做 runtime 測試。

## 4. 十張 callback 表的完整 index 41 結果

所有表相對 O；`41*8 = 0x148`。沿用已固定 `0x556D90..0x55E1E3` initializer 的入口證明和整段 SHA，核對所有賦值。

| 表基底 | index 41 slot | 入口與本次確認行為 |
| --- | --- | --- |
| `F0B6F0` | `F0B838` | `51BA90`：在總數尾端追加；初始化大記錄及第一組小記錄，插 map，增加 `+4`。 |
| `F0C110` | `F0C258` | `51BB50`：分類插入；必要時把原 `+C` 記錄單向搬到 `+8`，依首 byte 初始化大記錄；增加 `+8/+4`、更新 `+0`、插 map。 |
| `F0CB30` | `F0CC78` | `51BCC0`：以 ID 查 ordinal，初始化第三組陣列的兩筆 `0x2C` 內容，產出兩個 property 描述。 |
| `F0D550` | `F0D698` | `51BEB0`：entity 存在且 bit0=1 時執行 `7AEDF0`，之後派發另一個 peer 同步 helper。 |
| `F0DF70` | `F0E0B8` | **此 initializer 沒有 assignment**。 |
| `F0E990` | `F0EAD8` | `51BC40`：map 刪除、分類壓實與總数／前段數量調整。 |
| `F0F3B0` | `F0F4F8` | `51BEF0 → 7AFBE0`：移入 `+C` 分類前段。 |
| `F0FDD0` | `F0FF18` | **此 initializer 沒有 assignment**。 |
| `F107F0` | `F10938` | `51BF00 → 7AFFD0`：移出 `+C` 分類前段。 |
| `F11210` | `F11358` | **此 initializer 沒有 assignment**。 |

七個已登錄入口有確切 LEA/store bytes；兩個短 wrapper 各完整 8 bytes，以指標登錄證明入口。三個未賦值 slot **不能因此稱為 runtime null**：未捕捉可寫 callback table，也未在本次證明其初值或其他寫入。

## 5. 搬移、壓實與分類邊界

### `7AF210` 是單向 copy，不是 swap

參數：RCX=S、EDX=目的 ordinal、R8D=來源 ordinal；相同時直接返回。

- `7AF249/7AF24E`：來源 entity pointer 覆蓋目的 pointer。
- `7AF22A..7AF26E`：拷貝完整 `0x9928` bytes 大記錄。
- `7AF273..7AF2D1`：拷貝第一組完整 `0x58` bytes。
- `7AF2DA..7AF32D`：拷貝第二組完整 `0x58` bytes。
- `7AF336..7AF397`：由搬到目的的 entity ID 查 map，將 value 改成目的 ordinal。

來源槽未在此清零；只有搬過來的那筆 map value 被修改。八槽重新配置須讓所有四組資料仍隸屬同一 entity，且保留 map 修正。

### `51BC40` 的刪除分支

它先用 `S+0x50` 呼叫 `172F8A0` 刪除 ID 並取得 ordinal。若 ordinal 位於 `+8` 以外，減少總數 `+4`，必要時將最後總數槽搬入洞口；在已整合前段內，依 entity+0x14 bit0 分類調整 `+C`，再調整 `+8/+4` 並搬入相應尾端。具體 helper call／tail jump 在 `51BC8F` 與 `51BCB4`。

本次保留完整條件和 flags，不把每種刪除都簡化成一次無條件 swap。Map helper 找不到 key 的特殊回傳及異常輸入沒有被證明為安全使用情境。

### 移入／移出 `+C` 前段不同

- `7AFBE0`：查 ordinal，與 `+C` 邊界交換 entity pointer 和兩組小記錄，**目的大記錄清零**；修兩筆 map value，增加 `+C`。不是交換大記錄。
- `7AFFD0`：查 ordinal，与 `+C-1` 交換，**大記錄與兩組小記錄全部交換**；修兩筆 map value，減少 `+C`。

這與先前 roster 的分類搬移有相似模式，但本頁的結論来自元件 41 自身完整函式 bytes，沒有以相似性替代證明。`+C` 的通用 authority／本機玩家語義沒有在本頁命名。

## 6. 屬性記錄、第一槽特殊路徑與直接 owner consumers

### 第三組小記錄是必要資料，不是可覆蓋 padding

`51BCC0` 的 slot 取址為 `S+0x26688+ordinal*0x58`，將兩半 `0x2C` bytes 清零並拷貝到輸出 buffer。Property hashes 是 `0x1733B7A0` 和 `0x7F863207`，描述中的 type 值均為 `0xA`；本頁不猜字串名稱。

`7AF610` 接收一份 buffer 及 cursor：先由 entity ID 查 ordinal，`7AF69E/7AF6AA/7AF6B1` 形成同一第三組陣列記錄；拷入兩段 `0x2C` bytes，cursor 累計增加 `0x58`。因此第三組陣列也由 property 套用路徑直接寫入。

`51BEB0 → 7AEDF0` 的 post-setup 流程另有 **slot 0 特殊使用**：檢查 `S+C > 0` 及另一個模式条件，使用 `S+0x26688`、`S+0x266B4` 的兩半資料和 `[S+0x68]` 的第一個 entity pointer，經 `FD97E0` 派發上述兩個 hashes。不能因增加槽位就假設所有第一槽特殊讀者會自動遍歷八筆。

### 直接從 owner 取址的必要路徑

| 路徑 | 同一 owner／S 的證明 | 必須保留的存取 |
| --- | --- | --- |
| 更新 | `FDAEED RDI=context`；`FDAF4B RCX=context+40`；`FDAF4F call571250`；`57128D RDI=RCX`；`57142E R14=O+4148` | `571470..5715B8` 以 `+8` 迴圈，比較／複製第三組到第一組小記錄，讀 entity pointer。 |
| 整合待處理記錄 | `FDC78F RBX=context`；`FDC7A3 RCX=context+40`；`FDC7A7 call576CF0`；`576D0D RBX=RCX`；`577DDE RDI=O+4148` | `577DE5..577E2A` 依 `+8/+4/+C` 搬移記錄、增加分類邊界，最後 `+8=+4`。 |
| 屬性套用 | `BC2D85` 從已證 O 的 global346BFC8 取基底；`BD13E7 RCX=O+4148`；`BD13F5 call7AF610` | 第三組小記錄的完整 `0x58` bytes 寫入。 |
| 取消 registry | `55E203 RBX=entry owner`；`55F3A8 RCX=O+4148`；`55F3AF callB389B0` | 必須用與登錄時相同的 pointer 移除五張 registry 的副本。 |

Property 分派函式含間接 jump table；本頁固定了上述具體分支、owner 全域來源與 callee 的資料流，沒有另宣稱完整解決其所有訊息入口／動態可達性。

更新路徑在 `571484/57148C` 比較第二半 `0x2C` bytes，條件成立再把兩半共 `0x58` bytes 從第三組覆蓋第一組，然後呼叫 peer 同步 helper。只搬移其中一組小記錄會令比較與套用使用不同 entity 的資料。

此外已有 global-based 第一槽大記錄 consumer，例如 `FDFF33..FDFF94` 使用 `S+0x99A8` 內部 count 和 `S+0x88` 起點。這是保留第一槽與大記錄內部布局的重要例子；本次未展開大記錄全部內部欄位。

## 7. 八槽重新配置必須涵蓋的修改位置

這是已證明的必要集合，不是可直接套用的補丁清單：

1. **空間與生命周期來源**：owner+4148／next+2A930；constructor map 初始化；global publication；tag80 五個 registry pointer 副本；取消登錄 leaf。
2. **四組平行陣列**：指標、大記錄、兩組小記錄。新槽位不能覆蓋任何既有組或下一成員。
3. **加入與壓實**：已登錄的 `51BA90/51BB50/51BC40`，實際共用 copy helper `7AF210`，及保存程式內相關直接入口 `7AF7A0/7AFB50`。後兩者的存在不是其 runtime 被使用的證明。
4. **分類轉移**：`7AFBE0/7AFFD0` 的兩筆映射更新及大記錄初始化／交換差異。
5. **屬性與更新**：`51BCC0`、`7AF610`、`7AEDF0`、`571250` 的記錄基底與 derived-address 別名。
6. **外層整合**：`576CF0` 的 `O+4148` 直接別名及 `O+4154`（即 `S+C`）直接讀者；這些繞過 global3326998。
7. **Hash header 自指標**：`S+50 → S+10`。若複製或搬遷整塊 S，不能保留指向舊 block 的內嵌表 pointer。

正式 JSON 提供各完整函式的原 bytes、所有 fragments SHA、具體 memory operands 與 bounded global/helper reference scan。只比對固定 displacement 的清單不含所有由 `lea/add` 派生的地址，不能宣稱它已是完整 native relocation manifest。

## 尚未閉合

- 其餘 globals／helpers 對大記錄內部資料的全部用途，以及完整 native relocation 方案。
- 缺少 initializer assignment 的三張 callback slot 的 runtime 值。
- 所有高水位／分類初值與狀態轉換在實際 session 中的不變條件；本頁僅描述已見指令。
- 第五至八位真人的加入、同步、退出、重新加入與完整遊戲流程。第四次擷取未授權且本次未嘗試。

## 重播

輸出路徑必須尚不存在：

```powershell
python -B five_player_feasibility_20260927/component41_lifecycle_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output NEW-component41-lifecycle.json
```
