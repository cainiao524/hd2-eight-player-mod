# 2026-10-04 實機探針啟動記錄

## 執行範圍

依目前授權，曾把 workspace 建置的 `eight_player_pluginw64_release.dll` 暫時複製到固定 Steam build `25480438` 的 `bin/plugins`，再透過 Steam 啟動遊戲。自訂 DLL 使用唯讀探針；沒有設置容量 patch marker，也沒有呼叫 admission、create、remove、entity 或其他寫入型 API。

## 結果

- 自訂 DLL 暫存後啟動的程序 PID `39916` 很快顯示 `Fatal Error!`，沒有產生 2026-10-04 探針 log。
- 移除暫存 DLL 後，以官方插件再次啟動的程序 PID `18216` 也顯示 `Fatal Error!`。
- 兩個程序均已停止；官方 `level_generation_pluginw64_release.dll` 與 `wwise_pluginw64_release.dll` 未修改，自訂 DLL 已移回 workspace 證據目錄。
- 沒有取得新的 `setup_game`、GameSession、peer 或角色資料；這次嘗試不增加 runtime 或 multiplayer 證據。

## 判定

這是啟動環境失敗，不是第五人拒絕，也不是八人成功。保持 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。下一次實機工作應先解決遊戲正常啟動／可見視窗條件，再重做同一唯讀探針；不得以既有 `%TEMP%` 舊 log 冒充本次結果。
