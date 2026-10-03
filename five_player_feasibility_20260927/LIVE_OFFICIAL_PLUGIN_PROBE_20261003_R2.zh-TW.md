# 官方插件 `setup_game` 載入觀察（2026-10-03）

固定 build `25480438` 的 PID `42132` 再次載入自建 `eight_player_pluginw64_release.dll`。本次探針補上公開 Stingray `PluginApi.setup_game` callback；`loaded` 時 C API 尚未可用，但 `setup_game` 階段取得非 null 的 `ScriptApi`、`Network` 與 `GameSession` table pointer。

收據中的 `C_API_ID=31` pointer 為 `0x7ff7c09a8d80`，`Network` table pointer 為 `0x7ff7c09abe30`，`GameSession` table pointer 為 `0x7ff7c09abb90`。探針只保存指標值，沒有讀取或呼叫任何 table function，沒有寫入、hook、注入、peer admission 或 player creation。完整記錄見 [live_official_plugin_probe_runtime_20261003_r2.jsonl](live_official_plugin_probe_runtime_20261003_r2.jsonl)，彙整收據見 [live_official_plugin_probe_20261003_r2.json](live_official_plugin_probe_20261003_r2.json)。

這使下一個安全研究邊界從「取得 C API」進入「固定 `NetworkCApi`/`GameSessionCApi` 欄位與生命週期」。仍未證明第五至第八名玩家可加入，正式 `installable=false`、`multiplayer_verified=false`。
