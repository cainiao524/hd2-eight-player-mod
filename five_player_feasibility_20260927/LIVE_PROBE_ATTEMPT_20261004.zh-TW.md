# 2026-10-04 實機探針啟動記錄

## 執行範圍

依目前授權，曾透過 Steam 請求啟動遊戲，隨後把 workspace 建置的 `eight_player_pluginw64_release.dll` 暫時複製到 `bin/plugins`。複製早於觀察到程序啟動，但實際 loader 時序未核實。EXE 檔案 SHA-256 與固定 build `25480438` 相符。沒有設置容量 patch marker，也沒有主動呼叫 admission、create、remove 或 entity 寫入型 API；本次沒有探針執行記錄，不能據此確認 DLL 是否曾被載入。

## 結果

- 自訂 DLL 暫存後啟動的程序 PID `39916` 很快顯示 `Fatal Error!`，沒有產生 2026-10-04 探針 log。
- 移除暫存 DLL 後，以官方插件再次啟動的程序 PID `18216` 也顯示 `Fatal Error!`。
- 兩個程序均已停止；官方 `level_generation_pluginw64_release.dll` 與 `wwise_pluginw64_release.dll` 未修改，自訂 DLL 已移回 workspace 證據目錄。
- 沒有取得新的 `setup_game`、GameSession、peer 或角色資料；這次嘗試不增加 runtime 或 multiplayer 證據。

## 判定

兩次啟動均只觀察到 `Fatal Error!` 視窗標題，未能讀取對話框內文，根因未診斷。移除自訂 DLL 後仍出錯，不足以判定第一次錯誤的原因。保持 `installable=false`、本次 `runtime_verified=false`、`multiplayer_verified=false`。下一次實機工作應先取得錯誤內文並恢復正常啟動，再重做已核對的探針；不得以既有 `%TEMP%` 舊 log 冒充本次結果。此次 EXE 及兩個官方 plugin 檔案雜湊已與先前固定值比較相符。

## 追加的乾淨重試

清空 `%TEMP%\hd2_eight_player_plugin_runtime_probe.json` 後，透過 Steam `-applaunch 553850` 暫時部署同一份 DLL。PID `15724` 顯示 `Fatal Error!`，20 秒內沒有產生新的探針 log，也沒有 `setup_game`、`update_game`、Session 或 peer 觀察。程序已停止，自訂 DLL 已移除；這次不採用共用暫存檔中較早的 loader 回呼作為證據。
