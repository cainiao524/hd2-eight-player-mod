# MenuScreenLoadout live image preflight（2026-10-03）

`live_loadout_layout_20261003.json` 是針對固定 build `25480438` 的唯讀 code-image 預檢收據。工具只讀取 `game.dll` 內 `index_slot_mapping_evidence_v2.json` 的 226 個已固定 RVA，每個 anchor 重讀一次，並核對模組列表與檔案指紋。

## 結果

- 226/226 個 anchor 與預期位元組相符。
- 226/226 個 anchor 在重讀時保持不變。
- 總讀取量 2,446 bytes，低於 64 KiB bounded budget。
- `game.dll` SHA-256：`2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e`。
- 本收據標示 `read_only=true`、`calls_made=false`、`writes_made=false`、`hooks_installed=false`、`heap_objects_read=false`。

這只證明固定版本的程式碼 anchor 在該次程序讀取期間一致。它沒有讀取 writable heap、沒有觀察 session/peer 或玩家實體、沒有建立第五至第八個角色，也沒有驗證安裝、多人連線或任務生命週期；`runtime_verified`、`installable`、`multiplayer_verified` 必須維持 `false`。

## 可重播工具

```powershell
& 'C:\Program Files\Python312\python.exe' five_player_feasibility_20260927/tools/capture_live_loadout_layout_20261003.py --pid 36900 --output five_player_feasibility_20260927/live_loadout_layout_20261003.json
```

工具拒絕覆寫既有收據；若程序不再是固定 build 或 anchor 不相符，會 fail-closed 並回傳失敗，不會執行任何遊戲函式、寫入、注入或安裝動作。
