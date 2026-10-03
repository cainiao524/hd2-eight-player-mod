# 官方插件載入觀察（2026-10-03）

固定 Steam build `25480438` 的遊戲程序 PID `20472` 載入了倉庫內建置的 `eight_player_pluginw64_release.dll`。模組列表同時包含官方 `level_generation_pluginw64_release.dll` 與 `wwise_pluginw64_release.dll`。本次只讀取模組列表，未修改官方 DLL。

插件記錄到官方 loader 呼叫 `get_plugin_api` 的 API id `0`、`18`、`19`，並收到 `loaded` callback。插件在 `loaded` callback 只查詢公開候選的 `C_API_ID=31`；此程序回傳為 null，因此 `Network` 與 `GameSession` table pointer 都是 null。完整 JSON Lines 原始記錄保留於 [live_official_plugin_probe_runtime_20261003.jsonl](live_official_plugin_probe_runtime_20261003.jsonl)，彙整收據見 [live_official_plugin_probe_20261003.json](live_official_plugin_probe_20261003.json)。

插件沒有呼叫遊戲函式、寫入記憶體、安裝 hook、注入其他模組、加入 peer 或建立玩家；`player_admission_proven=false`、`player_creation_proven=false`、`installable=false`、`multiplayer_verified=false`。這證明的是官方插件載入入口可觀察，不能作為第五至第八名玩家或多人成功證據。
