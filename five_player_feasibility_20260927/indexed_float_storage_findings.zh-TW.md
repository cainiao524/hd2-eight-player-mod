# 單一 network-index float writer：物件身分、四筆初始化與相鄰欄位衝突

日期：2026-09-27。只讀既有固定程式 capture；未查询或讀取活程序、執行 probe、修改遊戲或總報告。

## 結論

`7275FA → 14335F0` 這個原先未收束的入口，現在可以列為**已證明的四筆區域容量衝突**。它按 roster network index `n`，將兩個 float 寫入：

```text
D + n*0x298 + 0x80E24
```

已接到同一個 D 的初始化函式，確認 `[D+80E18,D+81878)` 是四筆、每筆 `298` bytes 的區域。若此 writer 實際接收 `n=4`，寫入會部分覆蓋下一個已初始化子物件的首個 qword；若接收 `n=7`，則覆蓋另一已初始化子物件中會被清理流程使用的兩個 dword 索引欄位。**兩個索引都不能視為此陣列的可用空位。**

這是靜態條件結論，沒有觀察第五位玩家觸發寫入。caller 有其他狀態條件，也會跳過一個選定的本地 network index；因此不是「第五人必然到這裡、必然當機」的證明。D 的正式類別／精確 UI 用途仍保持未知。

## 1. caller RSI、D 與 initializer 是同一種物件地址

使用三個名稱避免混淆：

- `O`：既有 component owner。
- `M`：此入口所屬 manager，`M=O+1F7AE8`，global `3326AA0`。
- `k`：M 內實例索引；與 roster network index `n` 分開。

### update 路徑

1. `568236` 保存 `RBX=entry owner`；`5687E4/5687EB` 發布 `global3326AA0=O+1F7AE8`。
2. owner update `571250` 以 `57128D/571290` 保存 owner，經 `571F4A` 從 `[rsp+68]` 恢復 RDI。`571FF7/572001` 以 `O+1F7AE8` 呼叫 `725160`。
3. `7251A4` 令 `R14=entry RCX=M`。重播檢查整段前綴到 `727610`，沒有其他 R14 寫入。
4. `727516/72752C/727537` 形成：

```text
RSI = M + 4F90 + k*55A698
D   = RSI + 4C8260
    = M + k*55A698 + 4CD1F0
```

5. `7275F3/7275FA` 把 D 傳給 `14335F0`。

### 初始化路徑

`724260` 在 `724292` 直接讀同一個 global `3326AA0` 至 R13，並在此 manager 的 entity map 查出實例 ordinal。命中分支 `7245E4` 讀 map value 至 EBX；`724332` 算 `k*55A698`，`724340` 保存至 `[rbp-49]`，`72437C` 取回 RSI。

`7244E2/7244FD` 形成 `RCX=M+4CD1F0+k*55A698`，`724542` 呼叫 `142B990`。這與 update 路徑的 D 算式完全相同。R13 前綴只有 `724292` 的 global load；RSI 的中途借用與 `72437C` 恢復都保存在 replay，沒有僅靠相同 displacement 推論相同物件。

這證明同一個 manager 實例所用的子物件布局，並非宣稱這兩條路徑當前已執行。map 未命中而產生無效 ordinal 的行為也不是此次擴容結論的前提。

## 2. 確定只初始化四筆 `0x298` record

`142B990` 在 `142B9BE` 保存 entry D 至 RBX；直到該初始化段結束沒有改寫這個 base。

| 指令 | 已證實作用 |
|---|---|
| `142BB8D` | `R14=D+80EB8` |
| `142BB94` | `R12D=4` |
| `142BBA0` | 傳入清零起點 `R14-A0 = D+80E18` |
| `142BBA7/142BBA9/142BBAF` | zero byte 值、長度 `298`，call 固定 byte-fill helper `208AAA0` |
| `142BBB4..142BC27` | 在每筆記錄內初始化五個 `78`-byte 子物件 |
| `142BC2C` | `R14 += 298` |
| `142BC33/142BC37` | 迴圈計數減一，非零重複 |

因此：

```text
record 起點：D+80E18
record stride：298 = 664 bytes
初始化筆數：4
四筆末端：80E18 + 4*298 = 81878
兩個 float 位於各筆的 +C / +10
```

byte-fill helper 的大長度路徑已保存：將傳入 byte 展開，依固定程式選擇向量寫入或 `208AA80` 的 `REP STOSB`。沒有把未知外部 call 單憑慣用參數就稱作 memset。

接著 `142BC3D/142BC52` 以 **D+81888** 呼叫 `140C160` 初始化下一個獨立子物件。故四筆末端到下一已證成員只有 `10` bytes；那 `10` bytes 未被本研究全數命名，但也不夠容納第五筆 record。

這是陣列自己的可用區域及相鄰布局，並非 D 的整體 allocation 結束位址。D 後方仍有很多合法資料，不能因為寫入仍在巨大父物件內，就把它判成安全容量。

## 3. 寫入來源與條件

`72757E/7275B1/7275FF` 均讀已確認的 roster global `3326468`。迴圈以 roster count `+84` 控制 ordinal；`7275D2` 乘 `20`，`7275D6` 從該筆 `+3B4` 取得 network index `n`。

`7275DD/7275DF` 若 `n` 等於 EDI 保存的選定 index，會跳過這筆 writer；其餘從該 roster 記錄 `+3C0/+3C4` 讀兩個 float 至 XMM2/XMM3。

callee `14335F0` 在保存浮點參數後，`1433614` 算 `n*298`，`143362F` 進行 8-byte store。**在這次 store 前沒有 `n<4` 或其他容量檢查。** callee 後面再查 roster、檢查其他狀態，都已晚於這次寫入。

## 4. `n=4`：覆寫下一物件的 qword

```text
n=4 寫入：[81884,8188C)
下一子物件 B0 起點：81888
```

其中 `[81884,81888)` 暫未分類；但 `[81888,8188C)` 明確是 B0 首個 qword 的低 4 bytes。

`142BC3D/142BC52` 呼叫的 `140C160` 不是僅清零一塊沒有用途的記憶體：

```text
140C174  mov rbx,rcx       ; B0
140C19C  mov [rcx],rdx     ; 保存建構參數中的 qword
140C1A3  mov [rcx+8],r9    ; 同時保存 D
140C198  mov [rcx+10],rax
140C19F  mov [rcx+20],r8
```

其首個 qword 保存的是 initializer 傳入的 RDX（在 `142BC4F` 由 RBP 提供），不是經證明可閒置的 padding。這已足以確定 `n=4` 的第二個 float 會覆蓋既有成員的低半部；本輪未替該 qword 猜正式引擎名稱，也沒有推斷實際錯誤畫面。

## 5. `n=7`：覆寫另一子物件的兩個索引欄位

同一 D 的 initializer 還有一個 64 次迴圈：

- `142BA7E` 設定 R15D=`40`。
- `142BD5E` 設 R14=`D+81D10`。
- `142BD70..142BD98` 每次初始化兩個 `78`-byte 子物件，位置是 R14-78 和 R14。
- `142BD9D/142BDA4/142BDA8` 每次加 `180`，共 64 次。

其中迭代 ordinal 2 的第二個子物件為：

```text
B2 = D + 81D10 + 2*180 = D+82010
n=7 float store = D+[8204C,82054)
               = B2+[3C,44)
```

即覆蓋 B2 的 `+3C`、`+40` 兩個 dword。它們是 `+28` 起 dword 索引陣列的第 5、6 項（零起算）。

這個陣列有具體 reader：`140C200` 的 `140C226` 以 `+28+i*4` 讀索引；`140C22A` 將索引乘 `208`，從 `+20` 所指的 pool 取得元素位址，然後 call `1408F00`。迴圈按該子物件的 `+58` count 決定要處理幾項。

同物件的 cleanup 路徑也已接上：`7248D0` 由 global3326AA0 和實例 ordinal 建立同一 D；`724DF6` 呼叫 `142C9B0`。其中 `142CAA9..142CAD1` 依相同 `81D10` 起點、`180` stride、64 次計數，對每個 B2 類子物件 call `140C200`。

因此它不是僅在原位移附近找到相似資料：**D、初始化的 B2、清理時的 B2、B2 內索引 reader 都是同一條 base 計算鏈。** 若 `n=7` 的 store 到達，會寫入這兩個既有索引欄位；它們之後是否被消費，另取決於 count 是否包含第 5、6 項。沒有觀察到活程序中的 count 或索引值。

## 6. 容量判斷與命名界線

| network index | 寫入區間，相對 D | 本輪判斷 |
|---:|---|---|
| 0–3 | 每筆 `80E18+n*298` 內的 `+C..+14` | 位於已初始化的四筆區域 |
| 4 | `81884..8188C` | 部分覆寫下一個子物件的首個 qword |
| 5 | `81B1C..81B24` | 已超出四筆區域；本輪保留算式，未另展開所有欄位語意 |
| 6 | `81DB4..81DBC` | 已超出四筆區域；本輪保留算式，未另展開所有欄位語意 |
| 7 | `8204C..82054` | 覆寫 B2 的兩個 dword 索引欄位 |

若維持每筆完整 `298` 布局，四筆擴為八筆增加 `4*298 = A60 = 2656` bytes 邏輯記錄，原位末端會到 `822D8`。這不是只修改兩個 float 就能取得的免費空間，也不是已證明的最低新 allocation 大小。重排／外移時還要處理該記錄其他欄位的初始化、讀寫和清理，本輪只收束這個指定入口及必要的鄰接證據。

同一父 callback `724260` 中確實有原始 readonly 字串 `Galaxy_map_3d`、`Galaxy_map_2d_3d`；replay 保存文字 bytes 及其引用。但字串使用點没有把 D 當作已命名物件傳入，因此不把 D 正式命名為 galaxy map、minimap 或 HUD widget。此處保持「destination 子物件，精確用途未知」。

完全没有使用 `14A67D7` 的另一個 `298` stride 來證明身分。所有容量與覆寫判斷都以本入口的 manager global、owner offset、實例算式與 constructor / cleanup call 為基礎。

## 7. 可重播產物

- `indexed_float_storage_replay.py`
- `indexed_float_storage_evidence.json`：814 條保存的指令／pins；SHA-256 `11e984e270540eded0e141f821ddfbb22118c0b99645237eca15e14149d42378`。
- 固定前置 `roster_index_usage_evidence_v2.json` SHA-256：`d7098a7d698aa7daaf53e89c08b19cb01e243860f70fbba518690837baf121ee`。
- 原始 capture report SHA-256：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。
- 原始 capture data SHA-256：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。

重播核對原始來源與前置 SHA、unwind 指令邊界、完整短函式／多片段函式、關鍵指令、global RVA、base 暫存器前綴寫入集合及精確位移算式。輸出必須是尚不存在的新檔：

```powershell
C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe -B five_player_feasibility_20260927/indexed_float_storage_replay.py --evidence C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438 --output five_player_feasibility_20260927/indexed_float_storage_recheck.json
```

結論只針對固定版本的靜態條件；没有 runtime invocation、当前安裝資源一致性、第五人或八人測試，也没有製作可用 mod。
