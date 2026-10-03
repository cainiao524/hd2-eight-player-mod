# 固定版本 ABI 閉合收據（2026-10-03）

`verify_static_abi_closure_20261003.py` 只讀現有固定版本 `25480438` 證據，核對角色資源回調、角色建立門、回滾與執行緒靜默、peer lifecycle、配裝生命週期，以及 confirmed-peer 外部鏈。收據輸出在 `static_abi_closure_receipt_20261003.json`。

本輪結果：36/36 個一致性檢查通過；相關離線測試 48/48 通過。所有來源的 build 都是 `25480438`，並且保留 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。另外核對了目前公開 HD2Runtime／Better Lobby／Bingus loader 的 entry audit；它們仍只有觀測、資源載入與四槽讀取能力，沒有 peer admission 或 player creation writer。

新增 `join_handler_fixed_four_inventory_20261003.json`，把 host join handler 內 8 個字面量 `4` 完整分類：5 個是 capacity／peer／allocator／large-record 邊界，3 個是 protocol status／事件 metadata，後者不可盲目替換。這只是固定 build 的靜態分類，沒有產生 patch 或安裝器。

同時把 `external_party_playfab_capacity_audit_20261003.json` 接入閉環：Party/PlayFab 介面确實暴露網路配置與 lobby max-member API，但固定 event hash 沒有外部 DLL 命中，且沒有遊戲 native admission/player-creation bridge。這只排除把外部 SDK 當成目前可直接接線的入口，不能代替第五人實機驗證。

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
