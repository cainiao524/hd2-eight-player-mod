# HD2 多人容量 Mod：原始碼、證據與交接

Helldivers 2 eight-player mod research, offline native candidates, evidence, and handoff.

**2026-10-19 交接：目前沒有已驗證可玩的五人／八人 Mod。** 倉庫包含 `0.14.0-offline` 離線候選、後續容量與生命週期整合、只讀採樣工具及保存證據。六個 Party 入口已解碼，但共同 dispatcher、完整呼叫契約、真實加入／角色建立／同步仍未閉合。

`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`、`public_release_allowed=false`。歷史基線 `max_verified_players=4`；本次整理沒有重新進行遊戲或多人驗證。

## 接手入口

1. **[目前狀態與下一步](github_handoff_20260927/CURRENT.zh-TW.md)**：先讀這份，包含阻礙、授權狀態、工作順序和通過條件。
2. **[環境重建與離線驗證](github_handoff_20260927/SETUP.zh-TW.md)**：依賴、離線命令、原生建置說明。
3. **[證據索引](github_handoff_20260927/EVIDENCE_INDEX.zh-TW.md)**：最新報告、原始採樣、測試收據及其用途。
4. [完整目標](github_handoff_20260927/GOAL_OBJECTIVE.zh-TW.md)：八名真人、八個獨立帳號同任務的驗收範圍。
5. [機器可讀狀態](github_handoff_20260927/STATE.json)與[歷史交接](github_handoff_20260927/HANDOFF.zh-TW.md)：保留過往研究、已撤回判斷及來源指紋。

本次使用者授權的是整理與上傳。先前 PID 30776 的一次 v2 只讀採樣已完成，讀取 47,894 bytes；六入口解碼可確認四個命名 export。新的 dispatcher 補充工具預計讀取 33,018 bytes，硬上限 65,536 bytes，但尚未獲准執行。歷史文件中的實機、注入、安裝或測試授權不能自動延用。

容量契約支援 4/5/8/12/16 的設定與儲存邊界，這只屬離線設計能力。真實加入、角色建立、跨客戶端同步、增援與任務全流程仍須逐項驗證。

## 倉庫內容

| 目錄 | 內容 |
|---|---|
| `eight_player_candidate_20260927` | 離線候選、測試、合成產物與交付紀錄，包含尚未發布的後續工作 |
| `five_player_feasibility_20260927` | 研究工具、固定證據、重播結果與工作清單 |
| `research_handoff_20260927` | 共用 capture reader 與歷史研究來源沿革 |
| `github_handoff_20260927` | 完整目標、暫停狀態、重建說明及上傳清單 |
| `output/native_dispatch_20261010` | 精選保存證據與收據；保留原路徑供固定雜湊重播使用 |
| `evidence/existing-code-evidence-25480438` | 已有擷取的原始 report/data，供離線重播使用 |
| `FileDiver` 與三個參考目錄 | 已核對的必要資料及個別來源檔；來源子集詳見 SETUP |

保存證據保留原始 bytes，候選程式則包含本次收錄的後續工作。`.gitattributes` 停用換行正規化；可重建依賴及快取由 `.gitignore` 排除。檔名中的 `20261111` 是既有標籤，不應用來推斷實際採樣時間。此私人研究倉庫沒有發布新的可玩安裝包。

## 快照及上傳結果

[SNAPSHOT_SHA256.json](github_handoff_20260927/SNAPSHOT_SHA256.json) 列出目前資料提交中的檔案、大小及 SHA-256，清單本身不列入自身雜湊。遠端核對後由 [UPLOAD_STATUS.json](github_handoff_20260927/UPLOAD_STATUS.json) 記錄資料提交與驗證結果，再另行提交收據。2026-09-27 原始收據另存於 [archive/UPLOAD_STATUS_20260927.json](github_handoff_20260927/archive/UPLOAD_STATUS_20260927.json)，舊快照可按其 `payload_commit` 核對。

快照清單對應收據中的 `payload_commit`；後續上傳狀態更新不改寫原始快照清單。可執行：

```powershell
py -3.12 -B github_handoff_20260927/verify_snapshot.py
```

此命令只讀取 Git 物件並比對快照，不執行遊戲或研究測試。詳細用法見 [SETUP](github_handoff_20260927/SETUP.zh-TW.md)。
