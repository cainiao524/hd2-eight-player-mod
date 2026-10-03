# Official Plugin → GameSession 路線（2026-10-03）

## 公開 ABI

Autodesk Stingray 的公開 `engine_plugin_api/plugin_api.h` 定義：

- `PLUGIN_API_ID = 0`：plugin 自身的 `PluginApi` table。
- `C_API_ID = 31`：引擎提供給 plugin 的 `ScriptApi`。
- `ScriptApi` 的 `Network` pointer 位於 slot `7`（偏移 `0x38`），`GameSession` pointer 位於 slot `8`（偏移 `0x40`）。

公開 `c_api_game_session.h` 的 `GameSessionCApi` 包含：

- `add_peer(GameSessionPtr, uint64_t)`
- `peer(GameSessionPtr, unsigned)`、`num_peers(GameSessionPtr)`
- `remove_peer(GameSessionPtr, PeerId, callback)`
- `create_game_object*`、`destroy_game_object`、`migrate_game_object`

這些方法與八人生命周期所需的 peer／entity 操作形狀相符，因而是目前最實際的合法研究路線。

## HD2 限制

公開 Stingray header 是通用引擎 ABI，不代表 HD2 的 `25480438` 已把 Party/PlayFab 成員、confirmed-peer、Player Clone 建立接到這些方法，也不代表 `add_peer` 可以偽造遠端玩家。現有 plugin probe 只讀取 `C_API_ID=31` 返回的 `Network`／`GameSession` table 指標，不解參照 function pointer，也沒有呼叫任何遊戲 API。

## 可執行下一步

1. 在獲准的 plugin 載入觀察中保存實際 `ScriptApi`／`GameSessionCApi` table 指紋。
2. 只讀呼叫 `num_peers`、`peer(0..7)`，核對 generic session 是否仍只返回 `0..3`。
3. 找到合法的 Party member → `GameSession.add_peer` 事件邊界後，再把 `Native/Bridge` 八槽交易接到 player-resource／roster creation。
4. 對第五至第八人逐級測試 cleanup、reconnect、host migration；任一 callback 或 ABI 未閉合時保持 disabled。

目前狀態：`game_session_table_observed=false`、`player_admission_proven=false`、`installable=false`、`multiplayer_verified=false`。
