# 三個新增公開倉庫研究摘要（2026-10-03）

本輪只閱讀公開 README、技能文件和源碼，沒有複製其實現，也沒有把任何倉庫宣稱成八人方案。固定提交如下：

| 倉庫 | 固定提交 | 可採用內容 | 對八人實現的限制 |
|---|---|---|---|
| [MrChengl11/hd2-lua-mod-skill](https://github.com/MrChengl11/hd2-lua-mod-skill) | `d1811983ab4fec230ede24bdd3d274f77b0b82fd` | Bingus Shared Loader + LuaJIT FFI 的資料表／版本漂移研究流程；先離線，再做唯讀 runtime probe。 | 面向客戶端 Lua addon；沒有 peer admission、Party/PlayFab 容量或 Player Clone 建立證據。技能文件明確要求避免外部 `ReadProcessMemory` 和未驗證寫入。 |
| [junze0910/junze-hd2-lua-mod](https://github.com/junze0910/junze-hd2-lua-mod) | `95b2d26ea10ea43281c93123a95d326a289da2ae` | `hd2-scanner` 的 scanner、registry、UI 讀取模式，可作資料觀測工具。 | `src/tab.lua` 預設 `ALLOW_5TH=false`，並記錄第五個 UI tab 寫入實測會以 `0xC0000026` 崩潰；這是 UI 槽位風險，不是網路玩家槽位證明，也不可直接移植成 8 人邏輯。 |
| [starmatch666-droid/hd2-mod-update-skill](https://github.com/starmatch666-droid/hd2-mod-update-skill) | `2eae30596a0886b4674567f22f549ef03e9b80e4` | 以 `game.dll` SHA、RVA、table template 和 no-write fail-closed 狀態做版本更新與補丁鎖定。 | 這是更新／安全流程，不提供 session admission、roster 建立或多人生命週期實現。 |

## 對本專案的採用決策

1. 把第一個倉庫的離線優先、唯讀探測和版本漂移規則納入官方 plugin 證據流程。
2. 把第二個倉庫的第五 UI 槽位崩潰紀錄列為「不可把 UI roster 寫入當作玩家擴容」的反例。
3. 把第三個倉庫的 build/hash/table 門檻納入八人候選封裝；任何不匹配均保持 disabled。
4. 三個倉庫都沒有證明第五至第八個帳號可通過 Party → Session → Player Clone → Entity replication，因此本專案仍維持 `installable=false`、`multiplayer_verified=false`。
