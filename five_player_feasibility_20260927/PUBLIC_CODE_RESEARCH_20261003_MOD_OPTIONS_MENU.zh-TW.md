# Mod Options Menu 公開倉庫研究（2026-10-03）

固定提交：`CowboyBingus/ModOptionsMenu` main `46d693e421b44c4221ee6d984d26ea49997b948a`。

該專案是 Bingus Shared Loader 的客戶端原生選項介面。README 明確描述 Steam build `25480438` 的 game.dll/EXE hash 與 native entry point gate，選項以 Lua API 註冊、保存到本機檔案，並在 escape menu 內使用最多 8 個 mod category、每個 mod 最多 32 行。它提供的是安全的選項與版本漂移管理範例，不包含 Party/PlayFab member admission、GameSession peer writer、Player Clone 建立或 network entity replication。

對八人專案採用兩點：

1. 把「固定 build、hash、entry point 全部通過後才碰 native 路徑」納入 capacity/sidecar 的共同 gate。
2. 可以把未來八人模組的倍率、診斷等選項放在客戶端 UI，但 UI 顯示 8 個選項或 roster 行不能當作 8 個網路玩家證明。

目前仍禁止從 Mod Options Menu 推導玩家容量；`player_admission_proven=false`、`player_creation_proven=false`、`installable=false`、`multiplayer_verified=false`。
