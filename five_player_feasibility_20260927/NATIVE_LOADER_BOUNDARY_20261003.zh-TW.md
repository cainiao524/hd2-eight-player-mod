# 原生載入邊界審計（2026-10-03）

## 範圍

本審計固定 Steam build `25480438`，只讀檢查遊戲安裝目錄中的官方執行鏈、PE 匯出／匯入、已知 loader 字串，以及資料夾內可能影響啟動邊界的檔案。審計沒有啟動遊戲、沒有呼叫遊戲函式、沒有寫入程序記憶體、沒有安裝或注入。

機器收據：[native_loader_boundary_20261003.json](native_loader_boundary_20261003.json)

## 結果

- 官方鏈存在：`helldivers2.exe`、`game.dll`、`PartyWin.dll`、`PlayFabMultiplayerWin.dll`、`steam_api64.dll`、`lua51.dll`。
- `game.dll` 只列出 `get_plugin_api` 匯出；`helldivers2.exe` 靜態匯入 Party、PlayFab、Steam、Lua，但未發現使用者 Mod／Plugin／Loader 入口。
- 目前掃描沒有找到已知受支援的使用者原生 loader，故 `supported_native_loader_found=false`、`production_native_entry_proven=false`。
- `get_plugin_api` 仍是待解析的官方 runtime plugin API 候選；既有介面分析只證明 callback ID `31` 和 runtime table handoff，沒有證明可供八人 admission 或 player creation 使用。
- 安裝目錄內發現 `Havoc_Experimental.CT`、`Helldivers 2 Havoc Hub.exe`、`_internal/pyinjector/injector.cp311-win_amd64.pyd`、`files/bin/HH.sys`、`files/dxgi.dll` 等疑似注入工具檔案。它們被列為 disallowed injection artifacts，沒有被納入任何啟動、驗證或實作路徑。

## 對八人實作的含義

這份審計沒有提供可安全啟用第五至第八個 peer 的生產入口。既有原生 sidecar、receiver ABI 和 player-resource 合約仍是離線候選，不能由本審計升格成可安裝 patch。下一個可接受的研究方向是解析 `get_plugin_api` 的合法 caller、callback 實作、table `+0xf8/+0xa0` 以及服務端 lobby response；在這些資料閉合前維持 fail-closed。

狀態仍為：`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。
