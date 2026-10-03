# 官方插件 `GameSession` getter 觀察（2026-10-03）

固定 build `25480438` 的 PID `38132` 載入探針後，`setup_game` 取得公開 `ScriptApi`、`Network` 與 `GameSession` table。探針只呼叫兩個 getter：`NetworkCApi.game_session()` 與 `GameSessionCApi.num_peers()`。

記錄先看到 `session=0x0, peer_count=0`，之後在同一程序看到 `session=0x1900edd7e90, peer_count=0`。這表示官方 GameSession getter 可被實機讀取，且 session 生命週期由 null 進入已建立狀態；本次程序仍沒有已連線 peer。探針沒有呼叫 `add_peer`、`create_game_object`、`remove_peer` 或其他寫入型 API，也沒有寫記憶體、hook 或注入。原始記錄見 [live_official_plugin_probe_runtime_20261003_r3.jsonl](live_official_plugin_probe_runtime_20261003_r3.jsonl)，彙整收據見 [live_official_plugin_probe_20261003_r3.json](live_official_plugin_probe_20261003_r3.json)。

這把實作邊界推進到可安全讀取 GameSession 狀態；下一步是固定 peer getter、roster/player creation callback 與 host/client cleanup，仍不能把單程序 `peer_count=0` 當作多人成功。
