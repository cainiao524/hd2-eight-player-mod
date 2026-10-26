# HD2 多人容量 Mod：HellForge 適配主線

Configurable, extensible Helldivers 2 multiplayer targeting HellForge, including native player UI. Eight real players are the first major milestone; legacy evidence is preserved.

**2026-10-25：開發主線已轉向 HellForge 0.2.0-beta / SDK 13。** 新入口是 [HellForge 專案](hellforge_multiplayer/README.zh-CN.md)與[適配交接](hellforge_multiplayer/HANDOFF.zh-CN.md)。已有可編譯的 SDK 接入層與八個模擬後端節點測試；目前仍沒有已驗證可玩的五人／八人 Mod。

`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`、`public_release_allowed=false`。歷史官方環境基線 `max_verified_players=4`；HellForge 實機驗證人數為 0。這次適配沒有安裝、啟動、檢查或讀取遊戲。

**2026-10-26 方向更新：** 人數可配置、容量可繼續擴展，原生玩家 UI 與聯網／角色生命週期共同驗收。先第五人完整流程及 UI，再八名真人完整任務；八人不是長期架構上限。各子系統容量與實測人數分開記錄，見 [容量與 UI 計畫](hellforge_multiplayer/CAPACITY_UI_PLAN.zh-CN.md)。

元件 33 的完整資源需求收集與容量接納已接進現有名冊 owner 的整次呼叫範圍：六組 × 64 筆、包含重複取得次數；容量不足時，後續釋放／載入回呼不會執行。20 個自有進程情境、4,302 項檢查及三組保存指令的模擬對照通過。資源區、唯讀基準、B 與 20 個映像的既有壽命驗證繼續保留。這條新介面尚未綁定遊戲快照／服務或原入口，重置、嵌入資源交接、共同發布和原生 UI 仍待完成，詳見 [目前交接](hellforge_multiplayer/HANDOFF.zh-CN.md)。

## 接手入口

1. **[HellForge 適配與離線重建](hellforge_multiplayer/README.zh-CN.md)**：新 SDK Mod、固定上游、編譯命令和驗證結果。
2. **[目前阻礙與下一步](hellforge_multiplayer/HANDOFF.zh-CN.md)**：玩家容器的四槽限制、舊核心遷移關係及後續實施順序。
3. [舊路線交接](github_handoff_20260927/CURRENT.zh-TW.md)、[重建方法](github_handoff_20260927/SETUP.zh-TW.md)與[證據索引](github_handoff_20260927/EVIDENCE_INDEX.zh-TW.md)：保留歷史重播能力。
4. [完整目標](github_handoff_20260927/GOAL_OBJECTIVE.zh-TW.md)：可配置容量、原生 UI、第五人及八人主要里程碑的完整驗收範圍。
5. [機器可讀狀態](github_handoff_20260927/STATE.json)與[歷史交接](github_handoff_20260927/HANDOFF.zh-TW.md)：保留過往研究、已撤回判斷及來源指紋。

目前授權是遷移專案並適配 HellForge 源碼。先前 PID 30776 的一次 v2 只讀採樣已完成，讀取 47,894 bytes。舊 dispatcher 補充工具仍未獲准執行，亦不再作為 HellForge 源碼工作的第一前置條件。歷史文件中的實機、注入、安裝或測試授權不能自動延用。

容量契約支援 4/5/8/12/16 的設定與儲存邊界，這只屬離線設計能力。真實加入、角色建立、跨客戶端同步、增援與任務全流程仍須逐項驗證。

## 倉庫內容

| 目錄 | 內容 |
|---|---|
| `hellforge_multiplayer` | **目前主線**：SDK 13 Mod、原容量核心、八節點後端測試、固定來源與適配交接 |
| `eight_player_candidate_20260927` | 離線候選、測試、合成產物與交付紀錄，包含尚未發布的後續工作 |
| `five_player_feasibility_20260927` | 研究工具、固定證據、重播結果與工作清單 |
| `research_handoff_20260927` | 共用 capture reader 與歷史研究來源沿革 |
| `github_handoff_20260927` | 完整目標、舊交接、重建說明及歷史上傳清單 |
| `output/native_dispatch_20261010` | 精選保存證據與收據；保留原路徑供固定雜湊重播使用 |
| `evidence/existing-code-evidence-25480438` | 已有擷取的原始 report/data，供離線重播使用 |
| `FileDiver` 與三個參考目錄 | 已核對的必要資料及個別來源檔；來源子集詳見 SETUP |

保存證據保留原始 bytes，候選程式則包含本次收錄的後續工作。`.gitattributes` 停用換行正規化；可重建依賴及快取由 `.gitignore` 排除。檔名中的 `20261111` 是既有標籤，不應用來推斷實際採樣時間。此私人研究倉庫沒有發布新的可玩安裝包。

## 快照及上傳結果

[SNAPSHOT_SHA256.json](github_handoff_20260927/SNAPSHOT_SHA256.json) 對應 **2026-10-19 歷史資料提交**，不是本次 HellForge 適配工作區。當時的遠端核對由 [UPLOAD_STATUS.json](github_handoff_20260927/UPLOAD_STATUS.json) 記錄；本次適配有獨立[驗證收據](hellforge_multiplayer/evidence/offline-validation.json)。2026-09-27 原始收據另存於 [archive/UPLOAD_STATUS_20260927.json](github_handoff_20260927/archive/UPLOAD_STATUS_20260927.json)，舊快照可按其 `payload_commit` 核對。

快照清單對應收據中的 `payload_commit`；後續上傳狀態更新不改寫原始快照清單。可執行：

```powershell
py -3.12 -B github_handoff_20260927/verify_snapshot.py
```

此命令只讀取 Git 物件並比對快照，不執行遊戲或研究測試。詳細用法見 [SETUP](github_handoff_20260927/SETUP.zh-TW.md)。
