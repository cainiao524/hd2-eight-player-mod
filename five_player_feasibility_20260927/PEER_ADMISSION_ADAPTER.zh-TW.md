# Peer admission adapter 離線候選

這是把顯式 session 觀測接到八槽契約的純資料 adapter。它只接受呼叫者提供的 lobby、Party、host peer 和 client confirmed-peer 字典，沒有網路、FFI、遊戲程序、DLL、hook 或安裝操作。

## 接納規則

- 每組觀測必須帶相同的 caller-supplied `epoch`；epoch 不同或觀測欄位失效時，既有 latest inventory 會失效，直到重新提供同一輪的完整 preflight。
- preflight 必須有 `playfab_lobby`、`party_network`、`host_peer`，且 lobby／Party 為 `accepted`、未鎖定、user/member/device/endpoint 上限均有效。
- host peer record 必須逐項匹配 `member_id`、`peer_id` 和選定的 `network_index`；重複 member、peer 或 index 一律拒絕。
- 先保留 pending roster entry；只有相同 epoch 的 `client_confirmed_peer` record 和正確 reservation generation 才能 bind resource handle。
- `depart_peer` 與 `bind_resource` 都必須帶原 reservation generation。離隊保留 hole；重連建立新的 generation，舊 callback 不能作用到新 entry。
- `host_only` 和 `all_clients` 只是部署策略標籤。snapshot 固定 `native_adapter_present=false`、`live_ready=false`、`multiplayer_verified=false`。
- snapshot 另外保存目前 epoch；它是離線觀測批次的識別，不是平台 session token 或網路成功證明。

## 離線驗證

```powershell
& 'C:\Program Files\Python312\python.exe' -B -m unittest five_player_feasibility_20260927/test_peer_admission_adapter.py -v
```

目前 5/5 通過，涵蓋 0–7 分配、容量拒絕、host-only 標籤、失效觀測、pending→confirmed resource、離隊／重連 generation 和舊 callback 拒絕。收據見 `verification/peer_admission_adapter_verification.json`。

這些結果只證明資料契約和回滾行為；它們不代表 PlayFab／Party 已實際接受第 5～8 名玩家，也不代表任何客戶端能同步額外 entity。
