# 八人 Native Bridge staging package

這是可匯入 Arsenal/HD2MM 格式的 staging 骨架，不是已完成的八人聯機發布包。

`stage_package.py` 只有在下列條件全部成立時才會產生可啟用 staging 目錄：

- Steam build `25480438`、EXE `1.8.46015.0` 及六份檔案 SHA-256 完全相符。
- native admission plan 的 `executable` 為 `true`。
- plan 宣告八個 host/client slot、trampoline unwind、指令重定位、中段 capacity bridge、allocator sidecar continuation、sidecar lifetime、confirmed-peer dispatch 和 player creation gate。
- 固定 build 的 player-creation ABI、peer／confirmed-peer lifecycle、player-resource reverse cleanup、rollback/quiescence sidecar 與 MenuScreenLoadout relocation 審計存在且通過；staging 會核對八槽 peer map、partial callback 回滾、離隊／重連 generation、`FDC780 → FDC820 → FDDC80` cleanup 與 owner 靜默條件。這些報告只證明離線 evidence 完整，仍會保留 production／multiplayer 的 false gate。
- `Native/Bridge` 提供已測試的 sidecar orchestration candidate，會在 callback 缺失、build/site 不符、資源建立失敗或第九個玩家時 fail-closed，並在 admission 失敗時回滾。
- 額外提供 native bridge payload。

腳本只讀遊戲安裝目錄，輸出 staging 目錄和 `rollback.json`；不覆寫、注入或刪除遊戲檔案。即使 staging 成功，`multiplayer_verified` 仍為 `false`，需要五至八個獨立帳號完成實機驗收後才可另行發布。

Bridge 的合成 harness 只驗證 sidecar 與 callback 契約，不代表真實 Session／Party、game.dll 或多人同任務已接通。

## 為何沒有把 session admission 寫成 Lua/data patch

Bingus Shared Loader 的 addon 介面能載入 Lua 與 data archive。這條路徑沒有權限取代 PlayFab/Party peer admission、host/client confirmed-peer inline storage、Windows x64 trampoline/unwind 或 player creation gate。把 `MAX_PLAYERS` 或資料陣列改成 8 只會改離線資料，無法讓第五個 peer 得到一致的 network index，也不能安全修復原生 cleanup 和 host migration。因此本骨架把 `data/README.txt` 保留為明確標記，native payload 必須獨立通過固定版本 gate。

## 產生診斷和 staging

```powershell
& 'C:\Program Files\Python312\python.exe' `
  eight_player_candidate_20260927/Package/stage_package.py `
  --game-root 'F:\Game\Steam\steamapps\common\Helldivers 2' `
  --native-plan five_player_feasibility_20260927/native_peer_admission_plan_20261002.json `
  --diagnostics eight_player_candidate_20260927/Package/diagnostics.json
```

目前 plan 尚未可執行，命令會 fail-closed 並留下 blocked 診斷。
