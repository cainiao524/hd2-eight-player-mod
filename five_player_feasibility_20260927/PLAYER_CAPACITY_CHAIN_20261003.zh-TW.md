# Player/member capacity chain audit（2026-10-03）

這是固定 build `25480438` 的離線重播，來源為既有 `creation_path_evidence_v3.json`。它把多個獨立的四人假設分組保存，避免把單一 `4` 常數誤當成完整的八人接納契約。

## 已定位的分組

- owner capacity source：`0x10919D1` 將預設容量寫入 `owner+0x1B90`，並由初始建立與重建路徑讀取。
- initial member metadata：`0x10915DA` 以 `4` 建立初始成員 metadata。
- member enumerator：`0x1092E78`、`0x1092F31` 將 `4` 傳給 callback；`0x1092ECB`／`0x1092ED0` 進行四人 clamp/store。
- state update：`0x1093C91`／`0x1093C96` 進行四人 clamp/store，`0x1093D1E` 再以 `4` 傳遞容量。
- recreate：`0x1093A96` 將 owner capacity 加 `4` 後呼叫建立介面。

這些位點共同說明 session/member metadata、列舉、state update、重建和 player resource path 需要一致的 owner／callback／sidecar 契約。單改 `0x10919D1`、`0x1092ECB` 或任何一個常數，都不能證明第 5～8 名有唯一 network index、confirmed-peer、角色資源、roster 或清理生命週期。

`player_capacity_chain_audit_20261003.json` 的 11/11 固定檢查通過，但 `production_patch_ready=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false`。下一步仍需綁定 `owner+0x1B90/0x1BB0` 的實際 ABI、八槽 backing、拒絕／離隊／重連／房主轉移清理，並取得第五人真實流程。
