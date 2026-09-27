# 保存 bytes 的節點池驗證契約

## 成品需求與目前交付

此元件支援八人原型的資源生命週期與穩定性要求：在呼叫原生配置之前，核對提供的池、物件索引與模板資料能否用於容量規劃。它接收 Lua binary strings，不含程序讀取、FFI、loader、hook 或原生 executor。

新增的 [pool_snapshot.lua](Source/pool_snapshot.lua) 會產生標準化 snapshot，再交給 [pool_preflight.lua](Source/pool_preflight.lua) 計算原操作順序的完整配置需求。這完成了**提供資料的結構檢查**，未完成取得一致執行期資料的 adapter。

此階段停止條件是：有效的合成格式能接到 preflight；索引重複／越界、bitmap 與 used 矛盾、模板錯接、截短、區域重疊及已知空閒節點模式以外的資料都能被診斷；版本與部分配置限制保留。條件已由 [20 組離線測試](verification/pool_snapshot_tests.json) 達成。下一步應收束同步時點及剩餘共用池需求，不因測試通過就開始執行原生配置。

## API 與輸入

以已載入的 preflight module 建立 factory。依賴必須是受信任的本候選檔案。

```lua
local Preflight = dofile("Source/pool_preflight.lua")
local Snapshot = dofile("Source/pool_snapshot.lua")(Preflight)
local checked = Snapshot.validate(packet)
local plan = Snapshot.validate_and_plan(packet, operations)
```

這個範例只表示候選目錄中的離線 Lua 載入方式，不是遊戲 addon 入口。`operations` 保留既有順序，形式同 preflight。

| packet 欄位 | 格式／涵義 |
|---|---|
| `version` | `build`、`exe_sha256`、`game_dll_sha256`；與既有目標 profile 完全相等 |
| `d_address` | D 地址的 8-byte little-endian binary string |
| `game_base` | game.dll 基址的 8-byte little-endian binary string |
| `descriptor` | P 的完整 `0x20` bytes；P 由 `D+0x36F8` 推得 |
| `nodes` | 從 descriptor 的 nodes pointer 所指 backing 提供的 `capacity*0x208` bytes |
| `occupancy` | 從 descriptor 的 occupancy pointer 所指 backing 提供的 `capacity` bytes |
| `owners` | 一起算連續陣列：`{address=<8 bytes>, bytes=<完整 0x78 bytes>}` |
| `templates` | 一起算連續陣列：`{id=<0..72>, bytes=<完整 0xA0E8 bytes>}`；ID 不重複 |

地址不是 ASCII hex，也不是用浮點數傳入的任意 64-bit 值。候選只接受非零、低 canonical user 地址 `<2^47`，並檢查已知範圍結尾與對齊；此範圍可在 LuaJIT number 中精確表示。這不是 Windows page mapping 或可讀性驗證。

模板位置由 `game_base+0x3492F20+id*0xA0E8` 推得。必須提供所有占用 node 指向的模板、所有非零 requested ID 的模板，以及本批將請求的模板。模板清單不是完整的 73 模板 runtime 擷取；來源真實性由未完成的 adapter 負責。

4096 格 capacity／4096 個 owner／73 個模板是此解析器的輸入資源上限，沒有據此選定遊戲擴池容量。所有 table 都須沒有 metatable。地址、bytes 與模板是呼叫者提供的普通資料，模組不自行補抓缺少的記憶體。

## 核對的關係

1. Descriptor：capacity 有效、used 不超過 capacity、cursor 小於 capacity；backing 長度完全相符。
2. 物理區間：descriptor、nodes backing、bitmap backing、73 模板區及提供的 S 區間互不重疊；S 地址唯一。沒有對整個 D 的其他未列欄位作全域排除。
3. Bitmap：每 byte 限 0 或 1；完整掃描的占用數等於 used。
4. 每個占用 node：`N+8=D`，`N+20` 指向提供模板中的有效 element 起點，`N+28` type 與 element 相符。未被提供 S 認領的占用也會做這些檢查。
5. 每個提供的 S：`S+8=D`、`S+20=P`；requested ID 有效；active count 不超過 12 或模板數。
6. 每個 active index：在 capacity 內、指向占用 node，在提供的 S 中唯一；node 所屬模板與 element ordinal 符合 S 的配置前綴，且 context 三個 qword 與 `+18` DWORD 相同。
7. 每個模板 element：type 為目前支援的 1..4，event count 不超過物理十格。未檢查全部資源 payload、API handle 或 event 業務語義。

索引區只按 active count 讀取。Cleanup 可留下舊索引 bytes，不能因 inactive indices 是非零就拒絕資料。`requested_id=0, allocated=0` 是可辨識的空物件狀態；若操作明確要求模板 0，仍必須提供 count=0 的模板 0。這沒有證明實際 runtime 模板 0 的內容。

### 空閒節點的兩種已知模式

Occupancy 為 0 時，先要求 `N+20` template pointer 為零，再比較完整 `0x208` bytes。只接受：

- Cleanup 後：整個 node 為零。
- Fresh constructor 後：除了 `N+A8`、`N+AC` 的 DWORD 是 `0x3F800000`（1.0f），其餘為零。

第二種來自 constructor 清零後呼叫 `1408FE0`；該函式在 `1408FE9/1408FF3` 無條件寫入兩個 1.0f。若只要求整個 free node 為零，就會誤拒絕此初始化模式。其他模式回報 `unsupported_free_node_state`，意思是超出本候選契約，不能單據此宣稱遊戲記憶體已損壞。

最初版本只查 template pointer，會漏過 free node 中非零的 resource payload。本輪獨立審查提出後，新增測試先重現七個偽通過案例，再修正完整模式核對。見[審查與處理紀錄](verification/pool_snapshot_review.zh-TW.md)。

## 結果與整合限制

`validate` 成功回傳 `status="consistent_supplied_bytes"`、`executable=false`，以及：

- `snapshot`：新建立的 table，含版本、capacity、used、標準化 owner。
- `template_counts`：由提供的模板 bytes 讀得。
- `audit`：occupied／claimed／unclaimed 數、部分配置的 owner 身分、`all_occupied_nodes_accounted` 與範圍說明。

Owner 的 key 為地址的 16 位小寫十六進位字串，例如 `0000010000080da0`，不含 `0x`；操作必須使用同一 key。

`validate_and_plan` 在上述結構檢查通過後，直接呼叫 preflight，並附上 `snapshot_audit`。部分配置可以是結構一致的狀態，仍會在要求同 ID 時由 preflight 回報 `partial_same_id_requires_recovery`。

未提供 owner 的占用 node 會保留為固定其他需求。`all_occupied_nodes_accounted=true` 只表示所有占用節點在**提供的清單內**恰有一個認領者；它不能證明清單之外沒有舊 S 副本／外部 aliases。該欄位單獨不構成執行條件。

`fits` 只表示完整配置的容量算術成立。`state_semantics="full_allocation_plan_not_native_post_state"` 明示 steps、final_used、final_owners 都是假設各步完整配置成功的規劃值；尤其 `insufficient_capacity` 後的數字不能當成原生 partial 結果，也不能拿來覆寫恢復狀態。

所有狀態仍為 `executable=false`。尚缺：

1. 實際映像／模板來源與版本驗證。
2. 取得資料、preflight 到執行結束期間的同一同步保護；多次讀到相同 bytes 不能證明沒有競爭或重入。
3. 全部所有權、外部 aliases、資源 context 與 API handle 的有效生命週期。
4. 原生 executor、失敗恢復、完整共存需求，以及五至八人的遊戲測試。

### 主要診斷

| 診斷類型 | 常見 status |
|---|---|
| 資料／版本 | `invalid_input`、`invalid_length`、`version_mismatch`、`unsupported_address` |
| 池及占用 | `unsupported_capacity`、`invalid_used`、`invalid_cursor`、`occupancy_used_mismatch`、`unsupported_occupancy_byte` |
| 節點／空閒模式 | `stale_free_node`、`unsupported_free_node_state`、`invalid_template_pointer`、`node_type_mismatch` |
| 所有權／索引 | `duplicate_owner`、`region_overlap`、`duplicate_node_index`、`index_out_of_range`、`index_points_to_free_node` |
| Context／模板關係 | `owner_context_mismatch`、`owner_pool_mismatch`、`node_owner_context_mismatch`、`node_context_mismatch`、`owner_template_mismatch` |
| 模板／物件狀態 | `missing_template`、`duplicate_template`、`unsupported_template_count`、`unsupported_node_type`、`invalid_event_count`、`invalid_owner_state`、`owner_allocation_exceeds_template` |

失敗包含 `field`，部分另含 `index`。Owner／template 陣列位置一起算，slot／element ordinal 從零算；診斷使用位置須按該欄位解讀。無效資料不會被靜默修復或寫回。

## 驗證方式

在工作區根目錄，已具備本候選 `.test-deps` 的 Lupa 2.6 時：

```powershell
& 'C:\Program Files\Python312\python.exe' -X utf8 eight_player_candidate_20260927/tests/test_pool_snapshot.py
```

測試用 `lupa.luajit21`、`encoding=None` 直接執行兩份候選 Lua；Python `struct` 建立二進位資料。地址與 payload 是合成值，版型及選定模板節點／type／event 數以三份既有證據 SHA-256 固定。沒有新增遊戲程序操作。這些測試不宣稱合成 bytes 是保存的 heap，亦不證明八人 Mod 已能安裝或連線。
