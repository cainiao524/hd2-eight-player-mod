# Client 玩家索引的真正讀者：owner 內聯存取

## 本次補上了什麼

前次只檢查 `ClientSynchronizer` 字串所屬 root 與 client 附近的位移，未找到 scalar 讀者。本次改查**整個已保存 code 範圍**的 owner 內聯布局，找到可直接驗證的讀者與另一處 `<4` 條件。沒有讀取活程序、增加擷取或修改遊戲。

建構流程 `0x134D754` 從全域 `0x347CEF0` 取 owner；`0x134DD07` 建立 `client = owner+0x162C8`，`0x134DD28` 寫回 owner 指標。因此原本的 client 記錄可以換算為：

| 欄位 | client 相對位置 | owner 相對位置 |
| --- | --- | --- |
| confirmed-peer 筆數 | `+0xC8` | `+0x16390` |
| 第 i 筆 peer ID | `+0xD0 + i*0x20` | `+0x16398 + i*0x20` |
| 第 i 筆 host 指定的 player index | `+0xE4 + i*0x20` | `+0x163AC + i*0x20` |

完整位移掃描在 `+0x163AC` 找到 **64 個指令、49 個 unwind root**，另有 7 個 raw match 不在 unwind 範圍中。這些是候選，不把全數當作已證實的 client 使用者；例如 `0x183B632` 的相同位移出自另一個 base，尚未建立本物件來源。本頁下列已確認例子都回溯到同一個 `0x347CEF0` 全域 owner。

## 1. 已證實的 peer ID → network index 讀取及下游儲存

`0x631182` 取得 owner；`0x63118B–0x6311AD` 用 confirmed-peer 筆數及 0x20 步幅查找 peer ID；命中後 `0x6311C8` 讀取 `owner+0x163AC+i*0x20`。`0x6311D4` 檢查 `0xFFFFFFFF` sentinel。

此 index 會在 `0x63127D` 取回，於 `0x631296–0x6312A2` 成為另一個系統的 **24-byte 步幅**，寫入 `global[0x3326AE0] + 0xC4A0 + index*24`；另有 `+0xC4A8` 整數資料更新及 `+0xC4B4` byte 寫入。這證明索引確實供同步資料以外的儲存尋址使用，不能僅擴 client 名單便假設其他儲存可容納 8 筆。此下游儲存的容量及用途尚未確認。

## 2. network index 經過另一張表，才得到獨立槽位

`0xB90040` 遍歷 tag `0xE5` 註冊物件，與 client 並非同一物件。`0xB900C6` 從 owner 查給定 peer ID，`0xB9013B` 取出 network index，然後：

1. `0xB90143`：以 network index 讀 `registered_object+0x27D8+index*4`。
2. `0xB9014B–0xB9014E`：要求**該表的結果**小於 4。
3. `0xB90150–0xB90163`：用表的結果形成 `registered_object+0x620E8+result*0x1EE18`，傳給 `0x1893D40`。

這是有證據的「network index → 另一個槽位」映射。此處 `<4` 檢查的是映射結果，不能寫成 network index 的直接上限，也不能把它直接叫做 gameplay roster ordinal。`0x14719F0` 中也有同型內聯流程，可作後續交叉研究入口；本頁主要固定 `0xB90040` 的來源與位元組。

## 3. 新確認的直接 network index `<4` 條件

`0x1085D70` 的 `0x1086212` 取得同一 owner，`0x1086228` 取其 `+0xB398` 本地 ID，`0x1086238` 在 confirmed-peer 清單中找到該 ID。命中後，`0x108645C–0x1086469` 執行：

```text
shl rdx, 5
cmp dword ptr [rdx + r8 + 0x163ac], 4
jae 0x108624d
```

此處比較的已經是儲存的 network index，且為 unsigned 比較。**索引 4–7 會跳過 `0x108646F` 開始的特殊路徑**，即使前面的 confirmed-peer 筆數及記憶體已擴容也一樣。

小於 4 的路徑會準備資料、經平台介面間接呼叫 `0x10868BF`，將回傳 EAX 保存成 EBX，再呼叫 `0xFDC140`；最後 `0x10868F1` 呼叫 `0x608B60`，其中 RCX 來自已知 roster 全域 `0x3326468`，EDX 是上述 EBX。這是從 network index 條件接到 roster 方法的具體路徑。單靠這些指令尚不能把間接呼叫命名為玩家實體建立，也不能保證略過條件即可正常生成第五名玩家。

`0x1394FD0` 另有 inline 反向查找：在 EBP 小於 4 時遍歷 `+0x163AC` 索引，命中後從 peer ID `+0x16398` **讀低 32 位元**，並零擴展成 RDX。EBP 及該下游系統的含義尚未確定，保留為後續接點。

## 4. 無 unwind 的小函式：修正方法盲點，不把候選當已執行

在已知 client 函式之間的間隙，找到三個布局一致的 candidate：`0x10869B0` 本地 peer ID → index、`0x1086A00` 指定 peer ID → index、`0x1086A40` index → peer ID 低 32 位元。固定目標的全 code E8/E9 與 RIP MOV/LEA、保存區的 absolute pointer/RVA 查詢都沒有找到它們的已確認引用。因此它們目前仍是**結構候選**，不作已呼叫入口或玩法 dispatch 的證明。

另一個 leaf `0x1084FD0` 有兩個已驗證直接 caller：`0x10834B8` 和 `0x1083975`。它按筆數搜尋 peer ID 並回傳整筆記錄指標；但兩個 caller 分別在 `0x10834C2`、`0x108397F` 讀取的是 **record+0x18 的 byte**，不是 index+0x14。此已識別的 pointer escape 不構成 index 讀者。

## 可重播產物及接續方向

- `client_index_consumers_replay.py`：default 重新驗證本頁選定指令邊界、byte、unwind root、RIP 全域；`--rescan-fields` 可重跑 owner 範圍及小位移掃描。
- `client_index_consumers_evidence.json`：上述已證實群組及有 caller 的 leaf 完整 54-byte body。
- `client_index_consumers_field_scan.json`：全 code 位移候選與未受 unwind 覆蓋計數。
- `client_index_consumers_leaf_xrefs.json`：三個無引用 candidate 及 record-pointer leaf 的直接引用結果。
- `client_index_consumers_leaf_candidates.json`：間隙對齊解碼的探索資料，明確未把對齊當入口證明。

下一步應優先追 `0x608B60` 以及 `<4` 分支內平台呼叫的回傳 handle，用以確認這個條件保護的實際操作；並補齊 `+0x27D8` 映射表與 `+0xC4A0` 儲存的配置／清除／容量。原先「client index 尚無 scalar reader」的限制已被本次直接證據取代，但 **network index 與 gameplay roster ordinal 相等**仍然沒有證據。
