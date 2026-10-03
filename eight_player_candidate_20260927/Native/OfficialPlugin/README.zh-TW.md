# 官方 Stingray Plugin ABI 探針

此目錄保存固定 build `25480438` 的官方 native plugin ABI 探針。`get_plugin_api(unsigned)` 只接受 `api_id == 0`，未知 ID 會回傳 null；`loaded` callback 只查詢 `C_API_ID == 31`，再以公開的 `ScriptApi` 位置讀取 `Network`（`+0x38`）與 `GameSession`（`+0x40`）table 指標。探針不呼叫任何 table function，不讀寫遊戲資料，不建立 peer 或玩家。

目前已在實際遊戲啟動流程觀察到官方 loader 載入 `eight_player_pluginw64_release.dll`，並呼叫 `get_plugin_api` 的 ID `0`、`18`、`19` 及 `loaded` callback。該程序的 `C_API_ID=31` 回傳 null，所以還沒有可用的 `Network` 或 `GameSession` table。觀察收據位於 `five_player_feasibility_20260927/live_official_plugin_probe_20261003.json`。

`unloaded` callback 會清除所有保存的指標，避免使用 stale API。`build_x64.bat` 會建置探針 DLL、synthetic harness 和 `LoadLibrary`/`GetProcAddress` smoke test。

ABI 參考：[Autodesk Stingray plugin API samples](https://github.com/AutodeskGames/stingray-plugin-api-samples) 與 [Stingray engine plugin 文件](https://help.autodesk.com/cloudhelp/ENU/Stingray-SDK-Help/sdk_help/extend_engine.html)。

這是版本化的觀察入口，不是八人功能。必須先取得同一 build 的 `ScriptApi`/`GameSessionCApi` 真實 callback 合約，才能研究 peer admission、player creation、client cleanup 和 host migration；任何欄位或 callback 未確認時都保持 disabled。
