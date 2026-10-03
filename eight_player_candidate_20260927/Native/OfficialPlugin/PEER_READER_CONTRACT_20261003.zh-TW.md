# GameSession 唯讀 peer/record adapter 合約（2026-10-03）

此合約固定 Steam build `25480438`，同時核對 `helldivers2.exe` 與 `game.dll` 的 PE timestamp、image size 和 SHA-256。公開 Stingray C API 的 `Network` 與 `GameSession` table 位置（C API ID `31`，`+0x38`、`+0x40`）以及 `peer()`/`num_peers()` 偏移只保存為 ABI 參考；目前不能把它們當成 HD2 runtime 語義，也不會從 adapter 呼叫任何 vtable。

## 只讀範圍

adapter 只接收 `Native/SessionObservation` 產生的雙重穩定 snapshot 與 record semantics 結果，提供兩個讀取操作：

- `get_peer_count()`：回傳 bounded opaque record 數量，範圍 `0..7`。
- `get_peer_record(index)`：回傳 record 位址、已觀察的 identity token 和 byte `+0x29`。

這些欄位仍是 opaque relationship，不是 PeerId、player slot、network index 或 Player Clone 證明。

## 啟用前的硬性條件

缺少任何一項時保持 disabled：

1. 完整的 pinned build identity。
2. `opaque_session_records_not_player_proof` 與 `opaque_record_relationships_verified` 狀態。
3. `owner_acquire`、`owner_live`、`owner_release` 的 owner lifetime lease。
4. `quiescence_begin`、`quiescence_end` 的執行緒靜止區間。
5. `cleanup` callback，供 close/unload 釋放橋接擁有的資源。

adapter 的 `enable` 只在 quiescence 區間複製 bounded records；每次 getter 也重新檢查 owner 並進入 quiescence。`close` 先清空本地狀態，再執行 cleanup 和 owner release。任何版本、owner、snapshot、count、index 或同步錯誤都 fail-closed。

## 明確禁止的 runtime 操作

此合約沒有、也不會轉接下列 GameSession writer：

- `add_peer`
- `remove_peer`
- `create_game_object`

因此它不能建立第五個玩家，也不能宣稱 admission、玩家語義、安裝可用或多人成功。要進入下一階段，仍須另行取得同一 build 的 admission、player creation、replication、cleanup 和 host migration ABI，並以授權的實機證據驗證。

## 離線驗證

`build_peer_reader_x64.bat` 的 synthetic harness 已覆蓋：pinned identity、缺 callback、owner lease、quiescence、`0..7` bounded getter、第九筆拒絕、owner loss、cleanup，以及未證實 snapshot 的拒絕。測試輸出：

```text
official_peer_reader_contract_synthetic_passed
```

測試不存取遊戲程序、不呼叫 GameSession、不寫入遊戲記憶體，且不改變多人或 installable 門檻。

