# 固定版本 ABI 閉合收據（2026-10-03）

`verify_static_abi_closure_20261003.py` 只讀現有固定版本 `25480438` 證據，核對角色資源回調、角色建立門、回滾與執行緒靜默、peer lifecycle、配裝生命週期，以及 confirmed-peer 外部鏈。收據輸出在 `static_abi_closure_receipt_20261003.json`。

本輪結果：31/31 個一致性檢查通過；相關離線測試 44/44 通過。所有來源的 build 都是 `25480438`，並且保留 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。

這份收據只證明靜態 evidence 互相一致，不是可安裝 Mod。實機 staging 針對已安裝遊戲的診斷仍為 `blocked`：遊戲檔案雜湊正確，但 native admission plan 仍是 `executable=false`，而且沒有 production native payload。這表示目前尚未取得可安全載入的 resolver、owner/sidecar lifetime、confirmed-peer dispatch、第五至第八位角色建立及同步鏈。

驗證命令：

```powershell
python five_player_feasibility_20260927/verify_static_abi_closure_20261003.py `
  --output five_player_feasibility_20260927/static_abi_closure_receipt_20261003.json

pytest -q five_player_feasibility_20260927/test_verify_static_abi_closure_20261003.py `
  five_player_feasibility_20260927/test_verify_player_resource_callback_abi_binding_20261003.py `
  five_player_feasibility_20260927/test_player_creation_abi_gap_audit_20261003.py `
  five_player_feasibility_20260927/test_player_creation_chain_audit_20261002.py `
  five_player_feasibility_20260927/test_loadout_lifecycle_20261003.py `
  five_player_feasibility_20260927/test_loadout_sidecar_contract_20261003.py `
  five_player_feasibility_20260927/test_peer_lifecycle_sidecar_contract_20261003.py `
  five_player_feasibility_20260927/test_resource_rollback_quiescence_contract_20261003.py `
  eight_player_candidate_20260927/Package/test_stage_package.py
```
