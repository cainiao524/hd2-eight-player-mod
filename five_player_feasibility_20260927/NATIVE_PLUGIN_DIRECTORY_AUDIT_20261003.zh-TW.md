# 官方原生 Plugin 目錄審計（2026-10-03）

## 新發現

固定 build `25480438` 的 `bin/plugins` 不是空目錄。已確認兩個官方 Stingray plugin 模組：

| 模組 | SHA-256 | `get_plugin_api` |
|---|---|---|
| `level_generation_pluginw64_release.dll` | `67199c267805827fb2125ac4339ce7b37316357cbd361ec5130eae65750512de` | RVA `0x2140` |
| `wwise_pluginw64_release.dll` | `c78a9fa4eb3e93a07fd65aec26eaa86c909470210012327ae747b5d5615410b3` | RVA `0x42d10` |

兩個模組都 export `get_plugin_api`，與 `data/game/game.dll` 的同名 export 形狀一致。這證明遊戲存在官方原生 plugin ABI 候選，值得優先研究；它比未知注入或外部 loader 更接近可支援的 Mod 入口。

機器收據：[native_plugin_directory_audit_20261003.json](native_plugin_directory_audit_20261003.json)

## 仍未閉合的部分

- 尚未證明引擎如何枚舉、驗證、載入 `bin/plugins`，也沒有取得 plugin API table 的完整版本化 ABI。
- 尚未證明自訂 plugin 可以在不替換官方檔案的情況下被載入。
- 兩個官方 plugin 的 `get_plugin_api` 只證明 plugin 初始化入口，不證明它們提供 Session、peer admission、player creation 或 network spawn writer。
- 沒有新增、載入、執行或修改任何 plugin；沒有啟動遊戲程序，也沒有多人驗收。

## 下一個實作閘門

沿官方 plugin ABI 做靜態研究：比較 `game.dll`、`level_generation_pluginw64_release.dll` 與 `wwise_pluginw64_release.dll` 的 export table 初始化形狀，找出 plugin loader 的合法檔名／manifest／搜尋路徑與 API table 版本。只有在取得可重播的自訂 plugin 載入證據後，才把現有八槽 sidecar 接到 plugin 層；目前仍保持 `custom_mod_entry_proven=false`、`player_admission_proven=false`、`installable=false`、`multiplayer_verified=false`。
