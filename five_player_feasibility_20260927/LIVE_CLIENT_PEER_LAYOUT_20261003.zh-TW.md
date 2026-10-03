# live client peer layout 預檢（固定 build 25480438）

在程序 PID `45820`、固定 build `25480438` 上，對已保存的 owner→client 固定偏移執行兩次 bounded read-only capture：

- `live_client_peer_layout_20261003_r1.json`
- `live_client_peer_layout_20261003_r2.json`

兩次的 `session_owner`、`owner+0x162C8` client 位址、`client+0xC8` count、四筆 `client+0xD0` 起始的 `0x20` stride records，以及 `client+0x150` 起始的相鄰 `0x10` stride table 都相同。當時 session snapshot 同時觀察到一個 host peer `network_index=0`，但這個 owner/client 物件的 count 讀到 `0`、四筆 records 與相鄰 table 全為零。

這個結果只證明固定 offset 在該 menu／one-peer context 可安全讀取且兩次一致；它不能把零 count 解釋成角色不存在，也不能把 client object 當成已確認的 active peer registry。更不能由此推導第五人或八人已能建立。可能的 owner／state phase 差異仍需在真正 confirmed-peer／任務 context 中閉合。

工具 `tools/capture_live_client_peer_layout_20261003.py` 只讀已固定的 global、owner、client layout；沒有呼叫函式、寫入記憶體、安裝 hook 或注入。報告中的 `runtime_verified`、`installable`、`multiplayer_verified` 全部保持 `false`。
