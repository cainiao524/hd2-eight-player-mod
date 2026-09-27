# Roster 元件分派：旗標來源及 network index 屬性橋接

本支線沒有再重跑四個插入入口的精確 xref；改查相鄰 wrapper 的 ABI、資源處理的 creation params，以及其輸出欄位。只讀固定舊捕捉。`roster_component_binding_replay.py` 重新核對 196 個 unwind 指令邊界、22 條 caller 證明入口的 leaf 指令，以及固定 FileDiver 雜湊演算法與名稱來源。最新輸出為 **`roster_component_binding_evidence_v3.json`**，`runtime_verified=false`。v3 加入 network-index 顏色候選讀者的完整 fallback 和 readonly 數值。

這次的直接新證據是：**本地 network index 會被寫入 roster 的 0x20-byte 平行記錄 `+0xC`，並作為名為 `index` 的屬性 descriptor 輸出。** 這不是 network index 等於 roster ordinal 的證明。

## 1. 建立旗標不是未知的原生 bit 來源了

`0xFDC140` 的第四個參數 R9 是 creation params 指標；`0xFDC172` 保存到 RBP。新 entity record 的 `+0x14`：

1. `0xFDC1CD` 清為 0。
2. `0xFDC1D1` 檢查 `params[0]`。
3. 若非零，`0xFDC1D7` 將 record `+0x14` 設為 1。

同一 params 指標隨後傳給 `0x581320`。其第一組 callback 在 `0x58141B/41E/421` 使用 `(RCX=entity record, RDX=params)`。`0x540920` 取 entity 到 RDI，並在 `0x54094C` 檢查 `[RDX]`；該值非零時，會把新資料放入 `roster+0x88` 計數所界定的前段，必要時先搬移既有資料。即：**插入時的分類條件與 entity record `+0x14` bit 0 來自同一個建立布林值**。

另一支線正在將 component callback 靜態註冊表與上述 wrapper 接線；本頁的證據負責參數與欄位語義，沒有讀取執行期表值。

### 已知本地 player 建立路徑會傳 1

`0x1085D70` 原已確認的本地 peer/index `<4` 路徑，在 `0x1086830` 將 `[rsp+0x48]` 的 word 設為 1；`0x108684E→0x1086861` 複製至 `[rbp+0x2B0]` 這份 creation params 的首 16 bytes。`0x10868C2` 將其地址放進 R9，配上 `content/entities/player` 雜湊，在 `0x10868D7` 呼叫 `0xFDC140`。

因此這條已確認的本地 player 建立路徑會建立 **record `+0x14` bit 0 = 1**。這補上來源；尚不把這個 bit 在所有建立／後續修改路徑都統一命名為「local」或「authority」。也未證明每個客戶端永遠只有一筆此 bit 為 1 的 player record。

## 2. 相鄰 wrapper `0x540AE0` 可精確接上屬性產生階段

`0x581320` 的第二張表 `context+0xF0CB30+index*8` 在 `0x58152F` 呼叫目標，參數是：

| callback 入口位置 | 值 |
| --- | --- |
| RCX | entity record |
| RDX | creation params |
| R8 | 輸出 descriptor 陣列 |
| R9 | descriptor count 指標 |
| 第五參數 | 暫存 allocator 指標 |

`0x540AE0` 是有 unwind 的完整 wrapper，直接在 `0x540AF9` 呼叫 `0x60C640`。它把 entity record 移至 RDX、輸出陣列移至 R9、count pointer 放第五參數、allocator 放第六參數。`0x60C640` 的使用完全相符：

- `0x60C658` 讀 entity record `+8` 的 ID。
- `0x60C664` 保存 R9 為輸出陣列。
- `0x60C6C9–0x60C6DA` 取第六參數並配置 32 bytes。
- `0x60C6DF` 取第五參數作輸出 count 指標。

此外，**只有 creation params 首 byte 非零才執行這個屬性產生階段**：`0x58142D–0x581430` 為零時直接跳到 `0x5815AB`，略過第二張表的整段迴圈。不能把「取得本地 network index」推成每個遠端建立都會被寫成同一本地值。

## 3. 真正的 network index → roster 欄位 → 屬性 descriptor

`0x60C640` 先以傳入 entity ID 查 roster `+0xD0/+0xD8/+0xDC/+0xE0` 的 map，取得 **roster ordinal**。在 `0x60C6EE` 乘 32 後，選取 `roster+0x3A8+ordinal*0x20`。

`0x60C778` 的 E8 直接呼叫 **`0x134F190`**。此 leaf 沒有 unwind，但已有真實 caller 證明入口；本次從入口完整解碼 **92 bytes、22 條指令、兩個 RET**，所有條件分支目標都在已解碼邊界：

```text
0x134F190  取得 network owner global 0x347CEF0
0x134F199  讀 confirmed-peer count +0x16390
0x134F1A5  取得 embedded client +0x162C8 內的 owner backpointer
0x134F1AC  讀其本地 peer ID +0xB398
0x134F1C8  逐筆比較 confirmed peer ID +0x16398 + i*0x20
0x134F1E3  命中後讀 network index +0x163AC + i*0x20
```

未找到時回傳 `0xFFFFFFFF`。不能在第一個 RET `0x134F1DE` 就停止解碼，成功分支在後面的 `0x134F1DF..0x134F1EB`。

回到 `0x60C640`：

- `0x60C77D`：將返回 EAX 寫入 `roster + ordinal*0x20 + 0x3B4`，即此平行記錄的 `+0xC`。
- `0x60C784`：同值寫入新配置 buffer 的 `+0xC`。
- `0x60C78B/793/79C`：輸出 `{hash=0xB03B8BCE, type=1, pointer=buffer+0xC}`。

依固定 FileDiver `hash.go` 的 `Thin()` 定義，`upper32(Murmur64A("index")) = 0xB03B8BCE`。`index` 字串也直接存在捕捉 readonly RVA `0x2260E34`。這是精確 32-bit 名稱匹配，沒有聲稱雜湊唯一；數值來源是 network index 則由上述機器碼資料流直接證明。

### 一筆 entity 的八個屬性，並非八人容量

| descriptor 序號 | hash | type code | roster 相對欄位 | 初始值 |
| --- | --- | --- | --- | --- |
| 0 | `0x0F27C68E` | 1 | `+0x3A8 + ordinal*0x20` | `0x7FFF` |
| 1 | `0xCD889DBC` | 1 | `+0x3AC + ordinal*0x20` | 0 |
| 2 | `0x086C3722` | 1 | `+0x3B0 + ordinal*0x20` | 0 |
| 3 | `0xB03B8BCE`／`index` | 1 | `+0x3B4 + ordinal*0x20` | 本地 network index |
| 4 | `0x7ED6949C` | 2 | `+0x3B8 + ordinal*0x20` | 0 |
| 5 | `0xEBEE098F` | 2 | `+0x3BC + ordinal*0x20` | 0 |
| 6 | `0xBD74FB92` | 2 | `+0x3C0 + ordinal*0x20` | 0 |
| 7 | `0x83C8F804` | 2 | `+0x3C4 + ordinal*0x20` | 0 |

八個 descriptor 各為 16 bytes，由 count 指標追加；八個值合計 32 bytes。type code 保留數值，不憑類似其他介面的數字定義它的 SDK 型別。

## 4. 已確定的 index 讀者有顏色候選 fallback，不會在此拒絕第五人

`0x6054F0` 先用輸入 entity ID 查同一 roster 的 map，取得 ordinal（`0x605521–0x60567A`），再在 `0x605754` 乘 `0x20`，於 **`0x605760`** 讀出 `roster+ordinal*0x20+0x3B4`。這是剛才已證明存放 network index 的同一欄位。

`0x605767/0x60576A` 的 unsigned `<4` 分支，只保護一份 readonly 四筆表的讀取：

```text
index < 4:  0x213F4E0 + index*16 → 取該筆第1、2、3號float
index >= 4: 三個float均用readonly 0x23C6D70的1.0
共同尾部:   三分量乘readonly 0x23C79AC的255.0，組成12-byte buffer
```

這裡從零編號，每筆第 0 號 float 是 1.0，但這段輸出忽略它。實際前三分量排列如下：

| network index | 四筆表的原始 float（依序） | 乘 255 後的三分量（float32） |
| --- | --- | --- |
| 0 | `1, 1, 0.6156862974, 0.2588235438` | `255, 157, 66` |
| 1 | `1, 0.5058823824, 0.6745098233, 0.9960784316` | `129, 172, 254` |
| 2 | `1, 0.9647058845, 0.5411764979, 1` | `246, 138, 255` |
| 3 | `1, 0.4313725531, 0.8431372643, 0.3294117749` | `110, 215, 84` |
| 4–7（同樣適用其餘 unsigned >=4 值） | 不讀此表；三分量各 `1` | `255, 255, 255` |

三分量、正規化數值及 255 倍轉換高度符合 RGB 色盤，因此分類為**有完整保護的顏色候選讀者**，fallback 對應白色。精確的顯示位置或控制器用途沒有具名 API 證據，不能直接稱為 HUD 顏色或手把燈色。

`0x60579D` 另檢查未捕捉的 mode 全域 `0x347D620 == 1`，成立才於 `0x6057E6` 呼叫間接介面；RDX 指向這三個 float，RCX 來自未捕捉全域 `0x347D6A0`。指標鏈是：

```text
api          = qword[global 0x3326308]
first_table  = qword[api]
nested_table = qword[first_table + 0x10]
target       = qword[nested_table]
```

未捕捉的 mode 值、endpoint 物件及 target 名稱仍未知。無論 index 小於 4 或大於等於 4，兩條分支都匯合並繼續執行，**沒有由此 index 比較返回失敗或終止加入，也沒有 index 4–7 越界讀色盤**。八人實作可先保留此 fallback；若之後需要第五至第八人各有顏色，再擴色盤與 bound 即可。這不替其他尚未擴容的 roster／實體陣列提供安全保證。

### `player_count` 是稍後另一個具名呼叫

readonly **`0x22473C8`** 的確切字串為 `player_count\0`。`0x6058FF–0x605910` 把它傳到 RCX，EDX 為 `roster+0x84` 的實際筆數，再呼叫另一個介面：

```text
api    = qword[global 0x3326308]
table  = qword[api + 0x10]
target = qword[table + 0x480]
```

這個呼叫本身沒有把筆數限制為 4；它與前面的三分量輸出屬不同指標鏈。字串只能證明具名 `player_count` 參數已傳入引擎介面，尚不能把該 API 確定叫作音效、HUD 或 UI 設定，也不能證明 callee 接受／如何使用大於 4 的值。

## 5. 對八人 Mod 的具體影響與剩餘缺口

- component 的插入之外，後續屬性產生也直接存取 roster `+0x3A8` 四槽原布局。擴容／移動這個平行陣列時必須涵蓋 `0x60C640`，不能只改插入函式。
- 現在能把 network index 與 roster 記錄內的 `index` 欄位對上；仍必須區分「記錄 ordinal」與「欄位值」。後續應追屬性接收／套用與此 `+0x3B4` 欄位的使用者，確認第五到第八個 network index 沒有再被窄化或當四槽索引。
- 本次新追到的 `<4` 是有 fallback 的顏色候選讀者，可先保留；`player_count` 則按筆數傳值，但間接 callee 接受的範圍仍未知。兩者不應合併列為已證實的加入容量拒絕。
- 參數旗標來源及相同布林條件已固定，但 bit 在全部路徑的名稱、遠端接收值、狀態變更及 runtime 行為仍未完整驗證。
- `0x60CA80/0x60CBA0` 是與內聯 wrapper 相同布局／不同 ABI 的實作；這次沒有找到其本身另一條實際 dispatch，不用它們重複代替已定位的 wrapper callback。
- 本支線的 callback ABI、另一支線的 slot 註冊、資源所包含的 component 清單是三份不同證據。即使離線三者相符，也不能宣稱目前 live 遊戲已執行這條鏈，更不能宣稱八人已可遊玩。

## 產物

- `roster_component_binding_replay.py`：固定來源、196 條 unwind 指令、caller-proven 92-byte leaf、分支邊界、`index` 名稱薄雜湊、四筆色盤、fallback／倍率及 `player_count` 字串核對。
- **`roster_component_binding_evidence_v3.json`**：最新正式輸出。v1／v2 保留歷史；v3 加入 50 條 consumer 指令及 readonly 值。
- `roster_component_binding_name_matches.json`：八個 hash 在固定 FileDiver 名稱表及捕捉 readonly 可印字串中的限定查詢；只找到 `index`。
