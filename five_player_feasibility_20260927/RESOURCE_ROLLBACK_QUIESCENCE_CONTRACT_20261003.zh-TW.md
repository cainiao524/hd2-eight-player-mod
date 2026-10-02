# 玩家資源回滾、重入與 owner 靜默契約（固定 build 25480438）

`resource_rollback_quiescence_contract_20261003.py` 是建立在
`player_creation_abi_gap_audit_20261003.json` 與
`player_resource_reverse_cleanup_audit_20261003.json` 之上的離線資料模型。它把尚未被固定擷取證明的四個安全邊界，收斂成後續 native adapter 必須遵守的 fail-closed 契約：

1. **部分 callback 回滾**：callback 按 `first_callback → second_callback → roster_insert` 順序套用。任一階段失敗時，只撤銷已套用的階段，接著移除 roster 指標、owner+8 reverse map、resource handle 與 resource record；所有動作以反向順序記錄。
2. **重入冪等性**：每筆記錄包含 `network_index + generation + owner_epoch`。回滾或 release 的第二次呼叫只回傳原始 tombstone receipt；重新佔用相同 index 會增加 generation，舊 token 不得清理新記錄。
3. **owner migration**：owner 變更必須先進入 quiescence，且不能有 active resource record 或 callback lease。遷移成功時增加 `owner_epoch`，舊 owner token 隨即失效。
4. **thread quiescence**：每個 callback 都先取得 lease；尚有 lease 時不能 rollback、quiesce 或 migration。只有 callback lease 歸零且所有記錄清除後，才能發布 quiescent owner 狀態。

模型只使用 Python 記憶體中的資料結構。它不讀取遊戲程序、不呼叫 native 函式、不寫入記憶體、不注入、不安裝 Mod，也不宣稱第五至第八位玩家已經可用。

## 固定契約

- `logical_max_players = 8`，network index 僅允許 `0..7`。
- `record_ordinal`、`resource_handle`、`component_ordinal` 與 network index 分開保存；`component_ordinal = 0x7fff` 表示未分配 sentinel。
- 建構交易在所有 callback 完成前保持 `pending/active`，不能 `publish`。
- callback 順序錯誤、重複 lease、錯誤 owner epoch、布林值冒充整數、越界 index 與 generation 不一致都 fail-closed。
- rollback receipt 保存已撤銷 callback、清理動作、owner identity 和 generation，供重入時做純讀取回覆。

## 驗證

```powershell
pytest -q five_player_feasibility_20260927/test_resource_rollback_quiescence_contract_20261003.py
```

測試覆蓋部分 callback 失敗、反向清理、callback 順序違反、重複回滾、generation 防止 stale re-entry、active callback lease 阻擋 rollback/quiescence、confirmed record 阻擋 owner migration、成功遷移和輸入 fail-closed（目前 8 個測試）。合成 receipt 的 `production_patch_ready`、`runtime_verified`、`installable`、`multiplayer_verified` 全部保持 `false`。

輸出收據：`resource_rollback_quiescence_contract_20261003.json`。
