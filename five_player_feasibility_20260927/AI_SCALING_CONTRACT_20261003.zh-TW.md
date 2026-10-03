# AI Director 5–8 人安全行為契約（離線）

本文件固定同一份公開 DataLibrary 來源的現況，並定義八人候選在真正接上 native consumer 前可採用的安全資料契約。它只做檔案讀取和合成測試，不載入遊戲程序、不寫入資產或記憶體，也不代表多人已成功。

## 固定來源與現況

- build contract：`25480438`。
- 公開來源：[`Darctor/Helldivers2_RawData`](https://github.com/Darctor/Helldivers2_RawData) commit `52056ec` 的 [`HiveMindComponentData.json`](https://raw.githubusercontent.com/Darctor/Helldivers2_RawData/52056ec/Data/entities/HiveMindComponentData.json)。
- 來源 metadata：`game_version=1.007.100`、`patch_date=2026-09-22`、`exported_entity_count=19`。
- Git LF 來源雜湊：`b13dd18254513a2d8a6d14ae1a21262b7c3183fea4a36d3c950a7f2e0186d172`。本機 CRLF checkout 雜湊為 `a79632372c1ff16888cc636a9198b5efd5f0d8d711c42147a88dd18352f3b647`；重播只允許 CRLF → LF 這一種明示正規化，並記錄兩份雜湊。
- `player_count_multipliers` 出現 **247** 次，長度分布為 **247 個四項陣列**。其中包含 encounter、patrol、spawner、traveler 和 guard force 等多組 consumer 資料；不同欄位的四個數值並不相同。

這份資料只能證明 schema/asset 目前提供四個 player-count 值。它沒有證明 native consumer 的索引方式，也沒有證明 build `25480438` 與該公開快照完全相同；因此 receipt 仍把 same-build correspondence、native indexing 和 5–8 行為標為未證明。

## 契約

對每一個已驗證的四項向量 `v=[v1,v2,v3,v4]`：

| 玩家數 | 使用的索引 | 行為 |
|---:|---:|---|
| 1–4 | `player_count-1` | 使用原四項資料 |
| 5–8 | `3` | 明確沿用四人值 `v4`，不做外插 |
| `<1` 或 `>8` | 無 | 在索引前拒絕 |

另外必須滿足：

1. 向量必須恰好四項，每項為有限、非負數；缺項、超長、NaN、負值都 fail-closed。
2. host 與 client 使用相同 resolver；兩端獨立輸入的完整向量與 player count 都必須相等，即使不同 count 剛好產生相同 fallback 值也拒絕。這是合成一致性檢查，並非實際網路同步證據。
3. 啟用前要核對 build、來源 commit、metadata 和 SHA-256；任何版本不符都停用 AI scaling contract。
4. `5..8` 的 fallback 只處理 AI 倍率，不等於 peer admission、player creation、roster 或 entity 已擴容。

這個策略先保留四人已知預算，避免 5–8 直接索引不存在的資料項。未來若找到同 build 的真正 consumer，必須另提交其索引、clamp、host/client 一致性和負載測試證據，才能替換 fallback。

## 重播

```powershell
python -B five_player_feasibility_20260927/ai_scaling_contract_20261003.py `
  --source five_player_feasibility_20260927/ai_scaling_source_snapshot_20261003.json `
  --write `
  --output five_player_feasibility_20260927/NEW-ai-scaling-receipt.json

python -B five_player_feasibility_20260927/ai_scaling_contract_20261003.py --self-test
python -B five_player_feasibility_20260927/verify_ai_scaling_contract_20261003.py `
  --source five_player_feasibility_20260927/ai_scaling_source_snapshot_20261003.json
python -B -m pytest -q five_player_feasibility_20260927/test_ai_scaling_contract_20261003.py
```

已保存的收據為 [`ai_scaling_contract_receipt_20261003.json`](ai_scaling_contract_receipt_20261003.json)，測試為 20 項。來源可由本機 `public_research_20261002/Darctor_Helldivers2_RawData/Data/entities/HiveMindComponentData.json` 重播；來源本身沒有複製進交付 Mod。收據明確保留 `runtime_activation_allowed=false`、`installable=false`、`multiplayer_verified=false`，Encounter 與 Patrol consumer 都仍未定位。
