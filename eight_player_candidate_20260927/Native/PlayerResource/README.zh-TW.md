# Native PlayerResource sidecar（離線候選）

此目錄把固定 build `25480438` 的三張 callback table 交易順序做成八格原生 C++ sidecar：`begin → first → second → third → publish → release`。每個 slot 都有 generation、owner epoch、peer/resource identity 和 callback lease；部分 callback 失敗會清除記錄，重複 release 返回 `EP_RS_ALREADY_RELEASED`，owner migration 必須先 quiesce。

它只驗證 player-resource 的所有權與回滾契約，沒有解析遊戲 RVA、呼叫 game.dll、安裝 hook、注入程序或提供 player creation ABI。component `239` 只是測試輸入，對應固定 audit 的第一張 callback table roster leaf；真正 callback 仍需由已解析的遊戲 ABI 提供。

建置：

```powershell
cmd /c build_x64.bat
```

輸出 `ep_player_resource_synthetic_passed` 只代表離線 C++ 契約成立，`production_executable`、`runtime_verified`、`installable` 與 `multiplayer_verified` 保持 `false`。
