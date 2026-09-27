# 出生位置 RPC → 等待復活 → 物件 handle 的離線鏈

只使用 build `25480438` 既有 `game.dll` 捕捉。`respawn_receiver_replay.py` 重新核對 report／data 的固定 SHA，從 unwind fragment 起點驗證 216 處指令邊界，輸出 `respawn_receiver_evidence.json`。没有讀取活程序、執行遊戲函式或修改安裝檔；`runtime_verified=false`。

## 1. 六欄位事件已有本地等價處理與接收 wrapper

`0xAC7BE0` 在 `0xAC82CF` 選出 registry tag `0xB5`，於 `0xAC8303` 直接呼叫 `0xAC83F0`；緊接著 `0xAC8343` 呼叫送出 wrapper `0xBE1920`。兩者使用相同的 player object ID、12-byte 位置、另兩個 ID 值與兩個旗標。發送端供給 `0xBDE430` 的 hash 為 **`0x280728D6`**，descriptor 數量為 **6**。

| 欄位 | descriptor type／size | 發送來源 | `0xBA7390` 接收來源 |
| --- | --- | --- | --- |
| 1 | 1／4 | entry EDX 經 `0xFD9A40` 轉換 | descriptor `+8` 指標，經 `0xFD9BA0` 還原 |
| 2 | 3／12 | entry R8 指向位置 | descriptor `+0x18` 指標，讀 8+4 bytes |
| 3 | 1／4 | entry R9D 經 `0xFD9A40` | descriptor `+0x28` 指標，經 `0xFD9BA0` |
| 4 | 0／4 | 第 5 個參數的地址；目前 callsite 寫低 byte `1` | descriptor `+0x38` 指標，讀低 byte |
| 5 | 1／4 | 第 6 個參數經 `0xFD9A40` | descriptor `+0x48` 指標，經 `0xFD9BA0` |
| 6 | 0／4 | 第 7 個參數的地址；目前 callsite 寫低 byte `0` | descriptor `+0x58` 指標，讀低 byte |

`0xBA7419` 把這六個解碼結果交給 `0xB8E970`。該 handler 也篩選 tag `0xB5`，於 `0xB8EA09` 以同一欄位排列呼叫 `0xAC83F0`。因此這條語義鏈有直接等價的本地分派支持，並非僅依欄位數猜測。

捕捉的 readonly callback pointer run 在 `0x214C2E0` 起共有 592 項，`0xBA7390` 是零起算 **第 90 項**，entry RVA **`0x214C5B0`**。全捕捉範圍內的 plain little-endian hash 只有發送端 immediate 一處。這仍未直接證明 runtime registry 把該 hash 分派到該 wrapper。

## 2. 接收事件會寫既有名單的位置並設定狀態 2

`0xAC83F0` 的 `R8D` 是上述 player object ID，`R9` 是位置指標。`0xAC841F` 載入 roster global **`0x3326468`**；用 roster `+0xD0/+0xD8/+0xDC/+0xE0` 的 hash map 把 ID 查成 ordinal，`0xAC856F` 取 map value。此 ID 與 network peer ID／host 分配的 player index 不能視為同一數值。

通過 `ordinal < roster+0x88` 檢查後，`0xAC84D8/0xAC84E0` 寫入：

```text
roster + ordinal * 0x70 + 0x10C  ← position[0..7]
roster + ordinal * 0x70 + 0x114  ← position[8..11]
```

另一參數写 `+0x118`。對非 sentinel ID，`0xAC877C–0xAC8787` 以 `(roster, ID, 2)` 呼叫 `0x608A90`。後者再次查 ID→ordinal，將狀態寫至 **`roster + ordinal*0x38 + 0x2E0`**，即既有 0x38 記錄的 `+0x18`。

`0xACBE60` 的狀態分支與兩條停滯日誌直接對應：**2 = WaitingForRespawnTimer；3 = Spawned**。這是遊戲內原生狀態，不是推測的 RPC 狀態名稱。

## 3. 狀態 2 的下一跳現在已定位到物件 handle 產生邊界

同一 `0xACBE60` 更新迴圈在 `0xACC8CC–0xACC8E1` 要求 **ordinal 0** 及其 player 狀態物件 `+0x14` 的 bit 0。`0xACC926` 檢查 0x38 記錄狀態等於 2；接著經遊戲模式／計時條件，`0xACC97F` 呼叫 **`0xAC8800`**，EDX 為該 player 狀態物件 `+8` 的 ID。

`0xAC8800` 再次查 ordinal，讀取剛才名單 0x70 記錄的 `+4/+8/+0xC` 位置（`0xAC8B4E/0xAC8B6B/0xAC8BA1` 等），並計算生成所需資料。中間可以修正位置；目前未宣稱送入引擎的完整 descriptor 與收到的 12 bytes 逐位相同。

關鍵邊界為：

```text
0xAC9BE9  api = [global 0x3326308]
0xAC9BFE  object = [api + 0xC0]
0xAC9C08  vtable = [object]
0xAC9C15  target = [vtable + 0x18]
0xAC9C19  call target
          RDX = 0xB04D927AFB137B9B
          R8  = &stack descriptor
          EAX = returned handle
```

`0xAC9C2B` 保留回傳 handle 到 ESI。`0xAC9C4E` 把 `(roster, 同一 player ID, handle)` 交給 **`0x607820`**。該函式查得同一 ordinal，於 `0x60798D` 呼叫 `0x608A90` 將狀態設 **3／Spawned**，於 **`0x6079B5`** 把 handle 寫入 **`roster + ordinal*0x70 + 0x108`**（0x70 記錄的第一個 dword）。

這把出生位置接收、等待狀態、建立呼叫、handle 與 player 名單關聯串起來。它比單獨觀察可能的 allocator 有更直接的玩法資料流證據；但間接目標的名稱、實際分配器及成功結果仍未驗證。

## 對八人修改的影響與精確缺口

- 原本四候選更新現在可直接連到 handle 產生流程；這條具體分支只處理 **ordinal 0 且 player 物件 `+0x14` bit 0 置位**的情況。它可能用於各客戶端自己的玩家，但尚未獨立取得 bit 0 設定來源以確認「本機」語義，**不能將它改成八次無條件生成**。
- `0x608A90` 與 `0x607820` 是 ID→ordinal 後分別寫 0x38 狀態、0x70 handle 的具體存取端，需與 roster 搬移／擴容方案一致。
- 下一個底層缺口已縮成 **api+C0 所指物件的 vtable+18**。現有捕捉未含該 runtime 指標，不能根據這段間接呼叫命名特定引擎 API，也不能證明底層 entity 容量已支援八人。
- `0x280728D6 → 0xBA7390` 的 runtime hash 登錄仍缺直接資料；本地等價呼叫與六欄位 wrapper 已建立高信心語義對照。
- 未執行第五／第八名玩家加入、生成、同步、增援或結算；沒有產生可安裝的 Mod。

## 與 client-index 讀者的交會（補充）

另一路 `0x1085D70` 的 index `<4` 分支也使用相同的 `api+C0 → [object] → vtable+18` 形狀，於 `0x10868BF` 取得 EAX、保留成 EBX，再於 `0x10868F1` 把 `(roster global 0x3326468, EBX)` 交給 `0x608B60`。該 caller 的完整來源／index 保護由 `client_index_consumers` 的獨立證據負責；本次另保存 `respawn_receiver_608b60.json`，從該函式的 unwind fragments 解碼。

`0x608B60` 將傳入 EDX 當 **roster hash-map key** 查 ordinal，讀 0x20 記錄的第一個 dword（`0x608BDF`），經 `0xFD9BA0` 轉換；若有效，再拿 0x38 記錄的首個 qword 掃描八筆、stride 0xC0 的另一張表，命中才呼叫 `0x85CF90`。後續 player 物件 `+0x14` bit 0 置位時會發出單欄位 hash `0xE0294D95`。這裡沒有把傳入值當作 host player index，也沒有直接呼叫 `0x608A90` 或 `0x607820`。因此兩條路徑**共用同一未解析的引擎間接介面形狀，但不是同一個已證實的出生後狀態回調**；不能將其中一條的 index `<4` 直接當作另一條的 entity allocator 容量。

重播（輸出路徑須尚未存在）：

```powershell
python five_player_feasibility_20260927/respawn_receiver_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output NEW-respawn-receiver-evidence.json
```
