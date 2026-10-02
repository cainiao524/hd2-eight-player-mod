# HD2 八人聯機模組研究與交接

Helldivers 2 eight-player mod research, offline native candidates, evidence, and handoff.

**2026-10-02 已依使用者明確授權完成固定 build 的 live capture、native/session 入口核對與六檔 build preflight；native plan 仍為 `executable=false`，所以沒有安裝或注入。正式交付仍是 `v0.14.0-offline`，五人／八人實際聯機尚未驗證，目前沒有可安裝且已驗證可玩的八人 Mod。**

本輪也完成 [公開程式碼優先級核對](five_player_feasibility_20260927/PUBLIC_CODE_RESEARCH_20261002.zh-TW.md) 與 [Native Bridge orchestration candidate](eight_player_candidate_20260927/Native/Bridge/README.zh-TW.md)。Bridge 已在隔離 harness 驗證八槽 admission、callback 回滾、離隊與重連，但沒有接上真實 game.dll callback，也沒有多人驗收。

## 接手入口

1. [完整目標](github_handoff_20260927/GOAL_OBJECTIVE.zh-TW.md)：八名真人、八個獨立帳號同任務的完整驗收範圍。
2. [接續與歷史交接](github_handoff_20260927/HANDOFF.zh-TW.md)：已完成工作、尚未收尾的 6054F0 狀態更新候選與授權邊界。
3. [狀態與固定檔案雜湊](github_handoff_20260927/STATE.json)：目前本機交付與原暫停快照的指紋、後續工作。
4. [環境重建、來源與快照驗證](github_handoff_20260927/SETUP.zh-TW.md)：安裝離線依賴、使用倉庫內證據及核對 Git 快照的方法。

使用者已明確授權程序存取、載入／注入、安裝修改與真實多人測試，但所有操作仍受固定 build、可回滾 staging 和 fail-closed gate 約束。原上傳收據與快照清單保留2026-09-27的歷史驗證，不代表本次工作區更新已推送至GitHub。第四次擷取已完成；所有版本交付與多人結論以目前文件的實際範圍為準。

## 倉庫內容

| 目錄 | 內容 |
|---|---|
| `eight_player_candidate_20260927` | 離線候選、測試、合成產物與交付紀錄，包含尚未發布的後續工作 |
| `five_player_feasibility_20260927` | 研究工具、固定證據、重播結果與工作清單 |
| `research_handoff_20260927` | 共用 capture reader 與歷史研究來源沿革 |
| `github_handoff_20260927` | 完整目標、暫停狀態、重建說明及上傳清單 |
| `evidence/existing-code-evidence-25480438` | 已有擷取的原始 report/data，供離線重播使用 |
| `FileDiver` 與三個參考目錄 | 已核對的必要資料及個別來源檔；來源子集詳見 SETUP |

所有既有候選、測試報告與證據保留原始 bytes。`.gitattributes` 停用換行正規化；可重建依賴及快取由 `.gitignore` 排除。

## 快照及上傳結果

[SNAPSHOT_SHA256.json](github_handoff_20260927/SNAPSHOT_SHA256.json) 列出資料提交中的檔案、大小及 SHA-256，清單本身不列入自身雜湊。第一筆資料提交經遠端核對後，會由 [UPLOAD_STATUS.json](github_handoff_20260927/UPLOAD_STATUS.json) 記錄資料提交編號與驗證結果，再另行提交上傳收據和 `STATE.json` 更新。

快照清單對應收據中的 `payload_commit`；後續上傳狀態更新不改寫原始快照清單。可執行：

```powershell
py -3.12 -B github_handoff_20260927/verify_snapshot.py
```

此命令只讀取 Git 物件並比對快照，不執行遊戲或研究測試。詳細用法見 [SETUP](github_handoff_20260927/SETUP.zh-TW.md)。
