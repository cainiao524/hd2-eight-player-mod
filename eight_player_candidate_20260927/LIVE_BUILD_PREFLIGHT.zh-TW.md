# 固定 build 的 live preflight

`Integration/live_build_preflight.py` 只讀核對 Steam build `25480438` 的六份實際檔案：遊戲 EXE、`game.dll`、Party、PlayFab、資料型別庫與 generated entities。它也核對 `native_peer_admission_plan_20261002.json`、停止中的遊戲程序與重解析點，任何不符都拒絕 staging。

本機安裝的六個 SHA-256 均相符，程序已停止；但 native plan 仍為 `executable=false`，所以 `live_build_preflight_20261002.json` 的結果是 `blocked`。這個工具不複製、不注入、不修改遊戲檔案，也不把檔案核對或離線 sidecar 測試當作多人成功。

重現：

```powershell
& 'C:\Program Files\Python312\python.exe' eight_player_candidate_20260927/Integration/live_build_preflight.py `
  --game-root 'F:\Game\Steam\steamapps\common\Helldivers 2' `
  --native-plan five_player_feasibility_20260927/native_peer_admission_plan_20261002.json
```

只有在 native trampoline、Windows unwind、sidecar owner lifetime、confirmed-peer dispatch 與 player creation gate 全部有可回滾實作後，才可把 staging gate 推進；即使 staging 通過，仍須以五至八個獨立帳號完成同任務驗收。
