# 已知 owner 清單：四筆原布局與八筆獨立儲存

## 已完成的行為

[pool_owner_layout.lua](Source/pool_owner_layout.lua) 把已核對 constructor／cleanup 的訪問清單轉成實際可執行的 Lua 地址規劃與覆蓋檢查：

- 原四筆玩家 records：列出全部 **305 個已知 S**，其中 20 個屬玩家 records。
- 八筆玩家 records 使用明確提供的新基址：列出 **325 個已知 S**，其中 40 個屬玩家 records。
- 其他 **285 個 S** 保持原地址與訪問順序；包含 20 筆雙 S 陣列的全部 40 個物件。
- 不使用 active counters 裁剪清單。Count 歸零、停止顯示或跳過更新，不能代替 ownership 檢查。

這是候選 adapter 的地址規格，沒有讀取程序、配置記憶體、搬移資料、初始化 S、呼叫 cleanup 或修改遊戲。它沒有證明新地址已配置或全部外部 aliases 已轉移；所有結果為 `executable=false`。

## API

```lua
local Preflight = dofile("Source/pool_preflight.lua")
local Layout = dofile("Source/pool_owner_layout.lua")(Preflight)
local Snapshot = dofile("Source/pool_snapshot.lua")(Preflight)

local config = {
    version = observed_version,
    d_address = copied_D_address_bytes,
    player_records = {
        count = 8,
        base = allocated_record_base_bytes,
    },
}

local layout = Layout.plan(config)
local coverage = Layout.check_coverage(config, packet)
-- Only if coverage.status == "known_owner_addresses_complete":
local checked = Snapshot.validate(packet)
-- No result from this offline candidate authorizes native execution.
```

地址均為 8-byte little-endian binary string，不是 ASCII hex。`player_records.base` 是整筆 record 的起點，不是 `+A0` 的 constructor anchor。新 storage 的配置、大小、生命週期與來源由未完成的原生整合層負責。

`count` 只支援 4 或 8；第五人測試時可使用最終八份儲存，實際玩家數和儲存容量不能混為一談。原基址 `D+80E18` 只接受 4 筆，8 筆須提供其他儲存地址。四筆也可用指定的新基址作搬移規劃。

### plan 輸出

成功為 `status="known_owner_layout"`，包含：

| 欄位 | 用途 |
|---|---|
| `owners` | 按原 constructor／cleanup 順序的地址、16 位小寫 hex key、size、群組、record／member ordinal、fixed／player 分類 |
| `known_owner_count` | 305 或 325，限定已盤點的直接生命週期範圍 |
| `fixed_owner_count`／`player_owner_count` | 285 與 20／40 |
| `player_records` | 基址、筆數、`0x298` stride、完整 span 大小及是否搬移 |
| `protected_known_ranges` | 有限已知範圍，不是完整 D allocation map |
| `retired_player_owners` | 搬移時原 20 個玩家 S 地址，供 coverage 拒絕舊副本 |
| `inventory_evidence_sha256` | 產生布局所依據的固定 lifecycle 證據 |

Record index 和 member index 皆從零算；這是記錄及成員 ordinal，並未宣稱它們等同 network index、component ordinal 或玩家身分。

## 地址衝突檢查

整段玩家 record storage 都參與檢查，包括 S 之外的欄位與尾端 bytes。有限保護範圍包括：

- 285 個固定 S。
- 原四筆玩家 records 的完整 span；只有原基址四筆本身可重用該範圍。
- 原池 descriptor、256 格 node backing 與 bitmap。
- 已核對的兩張四格玩家 metadata 表。

候選檢查低 canonical 地址、8-byte 對齊與範圍末端，拒絕上述衝突。**通過不等於地址可用。** 其他 D 欄位、搬移後新的 pool backing、模板區、其他 allocation 或外部持有者仍需各自核對。Snapshot validator 會再檢查 packet 所描述的實際 P／node／bitmap／template／S 區間；整個 record 的完整原生配置契約仍待實作。

## Coverage 與 bytes 驗證的分工

`check_coverage(config, packet)` 要求 config／packet 都符合版本欄位，且 D 地址相同。每個已知 S 必須在 packet.owners 恰好出現一次。

- 缺少已知 S：`missing_known_owner`，附缺少數量與 keys。
- 重複地址：`duplicate_owner`。
- 搬移後仍列出原玩家 S：`retired_player_owner`。
- 額外 S 跨入應已停用的原玩家 record span：`retired_player_storage_overlap`。
- 額外 S 跨入目前選定的整段玩家 record storage：`player_storage_overlap`；已知玩家 S 本身除外，record 頭部與尾端也受保護。
- 其他額外 owner：允許列出，但以 `extra_owner_count/keys` 明示；其有效性仍須後續資料驗證。

成功為 `known_owner_addresses_complete`，同時回傳 `bytes_validated=false`、`requires_snapshot_validation=true`。它故意不把 bytes 長度、P 指標、active indices 或 resources 的驗證混入地址清單檢查。

因此資料來源需要依序滿足：**可信且受同步保護的資料取得 → 已知地址完整 → bytes／占用／索引一致 → 原操作順序的容量檢查 → 尚未完成的原生執行與恢復**。這些離線元件沒有完成前後兩端，也沒有排除所有未提供的 aliases。

## 證據、測試與停止條件

地址順序直接依據[生命週期投影](../five_player_feasibility_20260927/indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)，固定 SHA-256 `7722b443b293e565b1600fccbbb8820c0ef01e281f86aac237abb1419e20fda6`。新近[20 筆雙 S 證據](../five_player_feasibility_20260927/indexed_float_pool_double_records_findings.zh-TW.md)及[七個單例證據](../five_player_feasibility_20260927/indexed_float_pool_singletons_findings.zh-TW.md)進一步確認 count 與實際資源占用不可互換。

[23 組 LuaJIT 測試](verification/pool_owner_layout_tests.json) 的預期地址從固定 constructor／cleanup 投影轉換，沒有另抄候選 offset 清單作 expected。測試涵蓋：

- 全部 305／325 個地址及訪問順序。
- 八份只新增 20 個玩家 S，其他 285 個順序／地址不變。
- Count-zero 提示不會裁掉 40 個雙 S；移除該群組會精確回報缺少 40 個。
- 原地八筆、部分重疊與 record 尾端覆蓋被拒絕。
- 額外 owner 覆蓋目前 record 頭部／尾端但避開已知 S 的情況被拒絕；原四筆、搬移四／八筆均受保護，外側相鄰且不相交仍可接受。
- 搬移後每個舊玩家 S、副本、缺失、重複及額外 owner 的處理。
- 版本、位址邊界、對齊、稀疏陣列與 metatable。
- 305／325 個合成 fresh S 可接到 `pool_snapshot.validate`；只破壞一個 S 的 pool pointer 時，coverage 仍明示未驗 bytes，而 snapshot 回 `owner_pool_mismatch`。

可在工作區根目錄重現：

```powershell
& 'C:\Program Files\Python312\python.exe' -X utf8 eight_player_candidate_20260927/tests/test_pool_owner_layout.py
```

本項的離線停止條件已達成：可按已核對的布局自動產生完整已知清單並拒絕覆蓋缺口。下一步需把來源、配置、同步及所有 aliases 接合；不應以增加更多同型合成案例代替原生整合。此元件推進八人資料生命週期及穩定性需求，尚未完成任一多人驗收。

獨立審查、非 S 欄位碰撞反例及修正後核對見[審查紀錄](verification/pool_owner_layout_review.zh-TW.md)。
