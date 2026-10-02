# 固定版本 Live Build Preflight

`live_build_preflight.py` 是唯讀的固定版本前置檢查。它只讀取明確指定的遊戲根目錄、原生接納計畫 JSON，以及 Windows 程序清單；不會載入、注入、安裝、複製或修改遊戲檔案。

## 檢查內容

- Steam build `25480438`、EXE 版本標籤 `1.8.46015.0`。
- 六個固定 SHA-256：`bin/helldivers2.exe`、`data/game/game.dll`、`bin/PartyWin.dll`、`bin/PlayFabMultiplayerWin.dll`、`data/game/dl_library.dl_typelib`、`data/game/generated_entities.dl_bin`。
- 遊戲根目錄與所有檔案拒絕 symlink、junction 和其他 reparse point。
- 預設要求 `helldivers2.exe` 已停止；無法確認停止狀態也會 fail-closed。
- `native_peer_admission_plan` 必須是 build 25480438、八槽、`executable=true`，而且 `multiplayer_verified` 必須保持 `false`。

## 使用方式

```text
python Integration/live_build_preflight.py `
  --game-root "F:/Game/Steam/steamapps/common/Helldivers 2" `
  --native-plan "five_player_feasibility_20260927/native_peer_admission_plan_20261002.json"
```

成功結果的 `status` 是 `ready_for_reversible_staging`，只表示可以進入另行審核的可回復 staging 步驟；`live_ready`、`installation_authorized` 和 `multiplayer_verified` 仍固定為 `false`。原生計畫尚未 `executable=true`、任一雜湊不符、遊戲仍在執行或程序狀態無法確認時，結果為 `blocked`。

這個工具不會把磁碟雜湊、原生計畫標記或離線測試當作八帳號同任務成功。多人驗收仍須由八個獨立帳號和八個客戶端留下可複核的加入、戰鬥、死亡、增援、離隊、重連、撤離與結算記錄。
