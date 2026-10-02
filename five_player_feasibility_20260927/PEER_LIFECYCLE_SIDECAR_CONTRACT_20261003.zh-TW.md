# Peer／Confirmed-Peer 生命週期 sidecar 契約（固定 build 25480438）

`peer_lifecycle_sidecar_contract_20261003.py` 是對目前 peer admission 與 confirmed-peer sidecar 邊界的離線 fail-closed 模型。它只處理明確輸入的資料，不讀取遊戲程序、不呼叫 native 函式、不寫入程序、不安裝 hook，也不傳送封包。

## 已補上的契約

- `network_index`、member／peer identity、generation、resource handle 與 host owner 分開保存；八個索引只接受 `0..7`。
- confirmed-peer 建立分成 handle registry、component registry、confirmed dispatch 三步。任一步驟失敗都撤回已取得的 handle、component key 與 published key，原 reservation 保持 pending，可以安全重試。
- 離隊先進入 releasing；callback lease 尚未結束時拒絕 release 與 host migration。成功釋放後保留 network index 洞位，同一 generation 的重複 departure 回傳 `already_removed`，不會碰到重連玩家。
- pending reservation 的取消也是可重入的；重複取消回傳 `already_cancelled`，下一次佔用同一 index 會增加 generation。
- callback lease 以獨立 token 保存。重複 leave 是無害的，舊 token 無法取得新玩家的 callback lease。
- host migration 是 prepare／commit／abort 交易。準備時要求沒有 in-flight callback、沒有 pending／releasing record，並先驗證 index 與 identity；abort 不改 owner 或 roster，commit 才一次重建 map。peer identity 改變時提高 generation，阻擋舊 callback。

## 離線驗證

```powershell
python -m pytest -q five_player_feasibility_20260927/test_peer_lifecycle_sidecar_contract_20261003.py
```

目前 `8 passed`，涵蓋 partial confirmation rollback、pending cancel idempotence、departure idempotence、reconnect generation fence、callback quiescence、migration abort／commit、重建 map、token identity type guard 與 fail-closed 報告。

`peer_lifecycle_sidecar_contract_20261003.json` 的合成報告保留：

- `native_owner_quiescence_proven=false`
- `runtime_verified=false`
- `installable=false`
- `multiplayer_verified=false`

## 尚未閉合的原生條件

這個模型只證明 sidecar 資料契約與離線回滾規則。它沒有證明真實 native callback 的 register／stack／unwind ABI、owner lifetime、dispatcher binding、PlayFab／Party admission，或第五至第八個帳號的同任務行為。這些條件仍須在取得完整 ABI 與分階段聯機證據後才能解除阻擋。
