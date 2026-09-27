# network index 下游的 24-byte 儲存：四筆布局及連帶擴容範圍

## 結論

前次找到的 `global[0x3326AE0] + 0xC4A0 + network_index*24` **確實只配置成四筆相鄰記錄**。這次把來源、消費、清除及下一段有效儲存接起來：

- `0x631130` 以 network index 寫入 `+0xC4A0` 記錄。
- `0x631320` 先按另一份已登錄物件的次序建立 `+0xC440` 結果記錄，再按 peer ID 找到 network index，從 `+0xC4A0` 複製相符的 24 bytes；結尾只清掉 `+0xC4A0..+0xC500` 的 96 bytes。
- `+0xC500` 已是另一組有 key、整數／浮點數／布林值及 type 欄位的有效儲存起點。因此 index `4–7` 的寫入會越過這個四筆成員陣列，破壞同一物件的其他資料。這不是已證明會越過整個 heap allocation 的敘述。
- 同一系統另有三個加入實作的 `count+1 <= 4` 限制，以及位於物件末端的四筆指標／四筆 40-byte 記錄。只搬動 `+0xC4A0` 不足以讓此系統處理八人。

全部分析來自先前固定的保存資料，沒有讀活程序或新增擷取。正式系統名稱未由字串或符號證明；以下以 **tag `0x73` 系統**識別。它的用途可直接描述為保存與彙整 peer 對應的數值／旗標，並有型別化資料的網路序列化流程；不把它命名為某個已確定的樣本或獎勵系統。

## 1. 物件來源、內嵌布局及登錄

`0x568E12–0x568E19` 將 `owner+0x7C7368` 發布到全域 `0x3326AE0`。這與 constructor `0x5563CB`、更新流程 `0x57D953`、teardown caller `0x564D15–0x564D1C` 使用同一 owner 相對位置一致。下一個相鄰 owner 物件起點為 `+0x7FF1A0`，兩者相差 `0x37E38`。

constructor 在 `0x5563DC–0x556439` 建立內嵌 hash-map：儲存於物件 `+0x37D14`，其指標在 `+0x37D58`，bucket count `+0x37D60=8`。這裡的 8 是 hash bucket 數，不是八人容量。constructor 於 `0x5564B6` 呼叫 `0xB279D0`，後者在 `0xB279DF` 將 tag `0x73` 與物件指標一起放進多份登錄清單。

因此，將全域 `0x3326AE0` 改指別處並不等於搬移完成：owner 的直接內嵌存取、已登錄的物件指標及物件自己的內部 map 指標都仍需處理。

## 2. 24-byte 暫存寫入與消費

### 寫入路徑

`0x631149` 取 tag `0x73` 物件到 R14。`0x631182–0x6311C8` 從已確認的 network owner 查 peer ID 並讀 network index；只有 `0xFFFFFFFF` sentinel 被排除。後續 `0x631296–0x6312A2` 計算 `index*24`，把 peer ID 寫到 record `+0`。`0x6312D1` 從 record `+8` 起累加整數；其內層數目來自資料，這次沒有把它假定為三筆。`0x631305` 將一個 byte 寫入 record `+0x14`。

這個實作有已確認直接 caller：`0x11915A5`，RDX 來自 `0xFD9D40` 回傳之物件。這補足了入口有被程式引用的證據，但不代表這次遊戲執行過它，也尚未把此 caller 的狀態分支命名為某種特定玩法事件。

### 消費路徑

`0xACB137–0xACB13E` 以同一 global 物件直接呼叫 `0x631320`，故這個 consumer 的 RCX 來源已確立。

該函式先以六個 16-byte 寫入清掉 `+0xC440..+0xC4A0`，接著用 `+0x37D0C` 筆數遍歷 `+0x37D70` 物件指標。每筆 ordinal 決定輸出 `+0xC440+ordinal*24`。其 peer ID 再經 confirmed-peer 清單找到 network index（`0x6314E1–0x631559`）。若 `+0xC4A0+index*24` 內的 peer ID 相符，`0x631524–0x63153F` 以 16+8 bytes 複製整筆暫存到輸出；不相符時走另一套資料取得流程。

結尾 `0x6316C1/6C9/6D1/6D9/6E1/6E9` 是六個 16-byte 零寫入，清除範圍恰為 `+0xC4A0..+0xC500`。

**network index、tag `0x73` 系統物件的 ordinal、遊戲玩家名單 ordinal 尚未證明相等。** 本次已觀察到 network index 和本系統 ordinal 之間透過 peer ID 關聯，不能直接共用一套擴容索引假設。

## 3. 第五筆覆蓋什麼

| 目前成員陣列 | 起點 | 步幅 | 四筆後結束位置 |
| --- | --- | --- | --- |
| 彙整後的 peer 結果 | `+0xC440` | `0x18` | `+0xC4A0`，下一組暫存起點 |
| network index 暫存 | `+0xC4A0` | `0x18` | `+0xC500`，型別化儲存起點 |
| 已登錄物件指標 | `+0x37D70` | `8` | `+0x37D90`，已使用的 byte 區域 |
| 已登錄物件記錄 | `+0x37D98` | `0x28` | `+0x37E38`，下一個 owner 物件起點 |

`0x62D21A` 從同一 global 取得物件，`0x62D236–0x62D245` 以獨立的清除呼叫處理 `+0xC500` 開始、長 `0x2B800` 的區域。初始化流程還將落在此區域內的 typed-record 地址放進每筆物件記錄（`0x62D2A5–0x62D2D3`）。`0x62DF40` 直接消費這些 20-byte 記錄：`+0` key、`+4` integer、`+8` float、`+0xC` boolean、`+0x10` type，並交給既有 RPC descriptor sender `0xBDE430`。其輸入來源亦已核對：`0x1460C63–0x1460C71` 及 `0x146489A–0x14648A1` 從同一 global 取 RCX 後直接呼叫；另一條 `0xB856BF–0xB856ED` 從登錄清單選 tag `0x73` 物件後呼叫。`+0xC500` 不是閒置 padding。

| network index | 寫入 peer ID 的位置 | 寫入 flag 的位置 |
| --- | --- | --- |
| 4 | `+0xC500..+0xC508` | `+0xC514` |
| 5 | `+0xC518..+0xC520` | `+0xC52C` |
| 6 | `+0xC530..+0xC538` | `+0xC544` |
| 7 | `+0xC548..+0xC550` | `+0xC55C` |

其中 index 4 的 peer ID 寫入會同時覆蓋 typed-record 0 的 key 與 integer 欄位；其 flag 位於 typed-record 1 的 key 起點。以上是保存程式的確定地址運算，沒有聲稱已實際執行破壞。

## 4. 此系統還有三個四筆加入限制及搬移流程

三個入口 `0x53E130`、`0x53E1B0`、`0x631B90` 都先從 `global[0x3326AE0]` 取同一系統，檢查 `object[+0x37D08]+1 <= 4`；失敗路徑有明確的零地址寫入。

成功路徑使用 `+0x37D70+ordinal*8` 指標及 `+0x37D98+ordinal*0x28` 記錄，並維護 `+0x37D08`、`+0x37D0C`、`+0x37D10` 三個生命週期計數／位置。最後一筆 40-byte 記錄的末端剛好到相鄰 owner 物件 `+0x7FF1A0`。這讓擴大物件末端時會碰到相鄰物件的風險有了直接證據。

`0x631930` 搬移指標與整筆 40-byte 記錄，更新內嵌 map 的 ordinal。`0x631CE0` 還有一段內聯搬移。owner 更新函式在 `0x57D97F` 和 `0x57D990` 直接呼叫 `0x631930`。因此新增容量需要涵蓋加入、重排／清理及 owner 更新。

本次對三個加入入口的全 code E8/E9、RIP MOV/LEA 與 readonly absolute-pointer 搜尋尚未找到確立其實際 dispatch 的引用；不把「有實作」寫成「執行分派已閉合」。

## 5. 輸出記錄還有固定四筆的讀者

`0x126EB75` 讀同一 global。`0x126EBE7–0x126EBFF` 從 `+0xC440` 按 24-byte 步幅搜尋 peer ID，迴圈上限仍是 4。

`0x126EC60–0x126EC72` 直接將 `+0xC494`、`+0xC47C`、`+0xC464`、`+0xC44C` 四個整數相加。這些正是四筆輸出記錄的 `+0xC` 欄位。即使加入與暫存都擴大，只修改一處 loop bound 也不會使這種展開的四項加總涵蓋八人。

此段會向 `0x13F26F0` 傳不同常數，但本次沒有還原該介面的名稱，不把這些常數解讀為已確認的成就、樣本類別或結算項目。

## 6. 對實作的具體影響

這條下游已可列出明確的必要修改範圍：

1. 把 network-index 暫存與 ordinal 輸出記錄各自擴成八筆，並處理兩者地址被不同指令直接計算的情況。
2. 更新六次 16-byte 的固定清除、consumer 的 copy/read，以及固定四筆搜尋和四項加總。
3. 一併擴充本系統的物件指標、40-byte 平行記錄，保留既有計數／重排語意；核對內嵌 map 是否能在八個物件時正確運作。原有 8 個 bucket 不等於需直接改為 16，但若改 bucket 數，亦必須搬移底下儲存，不能令它覆蓋後面的 map descriptor 與指標陣列。
4. 若移動整個系統，修復 owner 內嵌取址、全域發布、tag `0x73` 登錄與 teardown 路徑；若採外置陣列，則需要補齊所有直接或算式存取者。
5. 閉合實際加入 dispatch 及資源名稱，才決定最小且完整的攔截集合。

本次未產生可用 patch；也沒有證明另一組引擎實體容量、網路房間容量或八人結算成功。

## 可重播資料

- `index_storage_capacity_replay.py` / **`index_storage_capacity_evidence_v2.json`**：7 組、247 個不同指令位置，均重新依 unwind 邊界解碼並保存 byte、SHA-256、root、RIP target；含布局算術與 index 4–7 的實際碰撞位置。v2 補齊 serializer 的同物件來源；原 `index_storage_capacity_evidence.json` 保留較早的 231 點版本。
- `index_storage_capacity_field_scan.json`：全 code `+0xC460..+0xC580` disp32 候選。其他函式內相同位移、不同 base 的結果未被當作本物件證據。
- `index_storage_capacity_lifecycle_scan.json`：owner `+0x7C7368` 及 `+0x37D00..+0x37E40` 的候選與邊界。
- `index_storage_capacity_global_xrefs.json`：全域取用／發布的固定捕捉查詢。
- `index_storage_capacity_function_xrefs.json`：寫入、消費與三個加入入口的引用查詢。
- `index_storage_capacity_serializer_xrefs.json`：serializer 的直接 caller，包含 global 來源及 tag `0x73` 登錄來源。
- `index_storage_capacity_disasm.txt`：核心 reset、typed-record serializer 及 snapshot consumer 的完整 unwind-root 指令清單。
