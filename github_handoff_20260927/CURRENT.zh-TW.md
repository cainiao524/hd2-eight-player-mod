# 多人 Mod 接手說明 — 2026-10-19

> **2026-10-25 主線已轉移到 [HellForge 適配](../hellforge_multiplayer/README.zh-CN.md)，下一步見[新交接](../hellforge_multiplayer/HANDOFF.zh-CN.md)。** 以下是 2026-10-19 舊路線狀態。共同 dispatcher 採樣不再是當前 HellForge 源碼工作的前置條件，也沒有獲得新的執行授權。

本文件保留舊路線進度；原日期採 Asia/Tokyo。保存證據原有時區、檔名和 bytes 不改寫。歷史授權、測試次數與當時的程序狀態，應按其收據日期理解。

## 交付判定

目標是八名真人、八個獨立帳號在同一任務中正常合作，並交付可安裝 Mod、原始碼、版本說明、安裝／移除方法與八人實測紀錄。第五人是中途里程碑。

目前是**可接續研究的離線候選與證據快照**。`0.14.0-offline` 是既有離線交付版本；此後新增的容量、native adapter 與採樣工作不代表新的可玩版本。尚無通過驗收的第五人原型。

| 門檻 | 目前值 | 含義 |
|---|---|---|
| `provider_binding_proven` | false | 真實 Party／Session 接入契約未閉合 |
| `installable` | false | 尚未具備可交付的多人安裝整合 |
| `runtime_verified` | false | 整體多人候選未經實機驗證 |
| `multiplayer_verified` | false | 沒有五人／八人完整實測 |
| `public_release_allowed` | false | 不作公開可玩版本發布 |
| `max_verified_players` | 4 | 沿用既有基線，並非本次重新測得 |

## 現有實作放在哪裡

| 子系統 | 主要入口 | 接手時要保留的行為 |
|---|---|---|
| 容量與 UI | `eight_player_candidate_20260927/Source/player_capacity_*.lua`、`Native/CapacityContract/`、`Native/CapacityControl/` | 版本／房主權限檢查、有效容量取最小值、任務中容量變更限制；16 格儲存不等於 16 人功能 |
| 接納與同步 | `Native/Bridge/`、`Native/ClientReplication/`、`Native/ClientSidecar/` | 原生建立、confirm、同步的順序；索引不符時在副作用之前拒絕 |
| 角色與資源 | `Native/PlayerCreationGate/`、`Native/PlayerResource/` | owner／generation 對應、部分失敗回滾、釋放失敗保留清理重試資料 |
| 載入與觀測 | `Native/OfficialPlugin/`、`Native/SessionObservation/` | provider 未綁定時拒絕啟用；不能把 EXE RVA 當作 game.dll RVA |
| Party 研究 | `five_player_feasibility_20260927/tools/party_manager_binding.py`、`decode_captured_party_entries_20261016.py` | opaque handle 不當普通指標解參照；保存資料解碼與真正呼叫分開判定 |
| 採樣 | `capture_live_party_slots_20261111.py`、`capture_party_dispatcher_supplement_20261016.py` | 指定 PID、固定版本、64 KiB、無自動重試、不覆寫輸出 |
| 兩客戶端驗收 | `capture_two_client_phase_20261011.py`、`verify_two_client_lifecycle_20261011.py` | 同一房間與階段連續性；兩客戶端結果不能證明第 5–8 人 |

表內未展開的 `Native/` 路徑均相對於 `eight_player_candidate_20260927/`；採樣工具位於 `five_player_feasibility_20260927/tools/`。

## 最近已取得的證據

一次 v2 只讀採樣已在使用者確認穩定單人飛船後完成，歷史 PID 為 30776。收據記錄 84 筆成功請求、47,894 bytes，低於 65,536 bytes；校驗前後一致，16 個 qword 復讀一致。採樣已結束，該次授權剩餘次數為 0。此 PID 和絕對位址不能當作目前狀態。

離線重播六個 wrapper，每條使用三組合成初值，均在共同間接呼叫之前停止。結果如下，RVA 僅對已固定指紋的 PartyWin 映像有效：

| 候選標籤 | PartyWin RVA | 可確認名稱 |
|---|---|---|
| create_network | `0x15720` | `PartyCreateNewNetwork` |
| async_or_state | `0x19880` | 未確認 |
| authenticate_or_state | `0x1BE80` | 未確認 |
| create_endpoint | `0x1C050` | `PartyNetworkCreateEndpoint` |
| connect_network | `0x14FE0` | `PartyConnectToNetwork` |
| auth_network | `0x1BC80` | `PartyNetworkAuthenticateLocalUser` |

共同槽 `EXE+0x2C75FEC` 指向 `EXE+0x2C7A94D`，入口跳到 `EXE+0x2EFAF2D`。最後這個目的地未在 v2 中讀取，已核對的保存視窗也未涵蓋。

共同呼叫前 `RCX/RDX/R8/R9` 在有限合成情境中保留，但 `RSP` 已向下移動 `0x20`。若把未知 dispatcher 簡化成 `JMP RAX`，有 stack 參數的 C API 會讀錯第五個參數位置。因此不能僅憑 export 位址吻合就製作直接轉接程式。完整傳參、回傳、owner lifetime、state changes、cleanup 仍缺證據。

## 接下來按什麼順序做

| 優先順序 | 工作與現有基礎 | 通過條件／依賴 |
|---|---|---|
| 1 | 依 SETUP 重建環境、核對快照、重播已保存入口 | 不接觸遊戲即可得到六個相同目標與未解決 RVA；缺檔或雜湊不符先解決資料問題 |
| 2 | 取得固定 dispatcher 視窗及兩個精確 export 名稱 | 需新的明確單次採樣授權及當前 PID；補充工具已完成，詳見下表 |
| 3 | 離線恢復 dispatcher 傳參／回傳與呼叫邊界 | 有實際保存 bytes 支持；若 4 KiB 不足，列出缺口，不猜填或自動追讀 |
| 4 | 閉合 provider／session／roster、角色建立、資源及同步 adapter | owner lifetime、失敗回滾、離隊重連和清理契約可核對；先補直接相關離線測試 |
| 5 | 按另行授權做兩客戶端基線 | 每台電腦一個客戶端；加入、退出、房主退出後的自動轉移或房間解散、清理有完整階段證據 |
| 6 | 第五人原型，再擴展八人任務全流程 | 原有四人相容；獨立帳號加入、生成、全客戶端同步、戰鬥、死亡增援、重連、撤離、結算及清理全部驗收 |
| 7 | 整理可玩交付 | 實測通過後才更新發布門檻、提供版本化安裝／移除與相容說明 |

使用者目前可提供兩台電腦、每台一個客戶端。飛船沒有手動轉移房主的步驟；應觀察原房主退出後遊戲自動行為。既有一次觀察是房間解散、客戶端返回自己的飛船，不能記成 migration 成功。兩客戶端完整驗收仍待補足。

## 待授權的補充採樣清單

此處是**未執行的下一步**。本次整理上傳不包含採樣、啟動遊戲、檢查程序、讀取安裝映像、注入、呼叫 native 函式或改寫遊戲。

| 指定範圍 | 單次 bytes × 次數 | 請求量 |
|---|---|---|
| EXE、game.dll、PartyWin.dll 的 PE header | 各 4096 × 2 | 24,576 |
| game.dll + `0x108C18F` | 76 × 2 | 152 |
| game.dll + `0x4EDAA4` | 36 × 2 | 72 |
| EXE + `0x2C75FEC` | 8 × 2 | 16 |
| EXE + `0x2C7A94D` | 5 × 2 | 10 |
| EXE + `0x2EFAF2D` | 4096 × 2 | 8,192 |
| **合計** | **16 筆請求** | **33,018** |

硬上限 **65,536 bytes**，含校驗、復讀與失敗請求。指定 PID 的路徑／模組／頁面屬性查詢，以及三份完整磁碟映像的指紋讀取不計入記憶體內容上限，仍屬需授權的讀取範圍。從已驗證 PartyWin bytes 精確查詢 `0x19880`、`0x1BE80` 的名稱／ordinal／forwarder；無匹配就保留未知。

執行順序：使用者明確同意此補充清單 → 手動進入穩定單人飛船並提供當前 PID → 執行一次工具、以新檔保存收據 → 關閉 handle → 僅離線分析。入口、版本、復讀或預算檢查不符即停止；不自動重試、不跟隨視窗內新分支。完整待執行模板保留在歷史 HANDOFF 最後一節。

## 驗證紀錄如何解讀

- 2026-10-19 本次驗證只覆蓋交接資料、離線工具、快照及 GitHub 上傳；結果見 [VALIDATION_20261019.json](VALIDATION_20261019.json)。已用僅含待上傳檔案的獨立副本與新建 Python 3.12 環境重做驗證：63 項測試通過、離線計畫及六入口重播與保存報告相同、v0.14 交付核對通過。沒有依賴原工作區的未入庫證據。
- 保存的 v2 工具測試為 45 項通過；dispatcher 補充工具為 18 項通過。本次按 SETUP 核對這三個測試檔的組合。
- 保存的呼叫邊界測試為 13 項通過、退出碼 0，但日誌記錄 21 筆 Unicorn `mem_map` 的 Windows access-violation 診斷；不能作為 native／遊戲穩定性證明。
- 保存的全套離線收據為 469 passed／3752 subtests passed；這是歷史結果，本次不以此數字宣稱整套重新通過。
- `STATE.json` 保留多次歷史觀察，舊 `true` 值須按欄位所在日期／範圍解讀；目前授權與門檻以 `current_handoff_20261019` 及本文件為入口。

## 檔案與維護約定

不要為了整理而重命名固定雜湊證據或改寫舊收據。新增報告使用新檔名。若修改來源，需同步相關 manifest／profile 的來源指紋，再驗證交付；不能以舊 receipt 證明新來源。

上傳保留多人專案既有追蹤檔、後續原始碼與必要產物，加入 `output/native_dispatch_20261010/` 的研究 JSON、選定測試日誌／XML、十二個恢復視窗與來源日誌。遊戲完整映像、依賴快取、暫存編譯檔、新的探針安裝包及其他 Mod 工作區不新增入庫。已有追蹤的歷史 native 建置產物保留，不作為可玩發布包。
