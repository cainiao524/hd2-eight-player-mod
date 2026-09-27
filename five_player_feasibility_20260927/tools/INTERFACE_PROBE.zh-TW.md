# 平台介面指標的限定唯讀擷取

`interface_probe.py` 用來補上先前捕捉缺失的執行期介面指標。**它是研究工具，不是八人 Mod。** 本輪先完成 `--plan`、9 項 mock 測試與獨立審查；之後使用者同意一次本機唯讀擷取並手動啟動遊戲，已於 2026-09-27 香港時間 12:02:53 完成。結果見 [本次擷取 JSON](../interface_probe_live_20260927_1.json)：讀取 17,224 bytes，版本／指紋檢查通過，指定欄位重讀未見變化。此結果只適用本次限定讀取，不能外推到其他版本、完整程序或多人玩法。

## 擷取目標

既有靜態分析在 `game.dll` 的加入平台流程看見間接呼叫，但缺少這些全域指標的值。工具限定讀取以下三條路徑：

| 路徑 | 保存資料 | 仍無法證明的事項 |
|---|---|---|
| `game.dll+0x3326308 → +0x30 → +0x18` | 介面與函式指標、函式所屬模組及 RVA、最多 256 bytes 程式前綴 | 實際 API 名稱、完整實作、參數意義。 |
| `game.dll+0x3326308 → +0xf8 → +0xa0` | 同上；這是先前建立流程中把設定值加 4 的呼叫目標 | 加 4 是否代表玩家容量、平台服務是否接受八人。 |
| `game.dll+0x3326340 → +0x20` | 32-bit 設定值 | 設定值為零時由呼叫端選預設 4；工具不呼叫該流程。 |

每次採集還讀取版本檢查所需的兩張 PE header page 和兩處程式指紋。總 `ReadProcessMemory` 讀取預算上限 64 KiB。輸出 JSON 只寫至明確指定的新檔案，包含指標、上述程式前綴、模組路徑與版本證據。沒有網路上傳。

## 版本與失敗處理

只接受 build `25480438` 對應的 `helldivers2.exe` 與 `game.dll` 完整磁碟 SHA-256，並核對載入映像的 PE 身分及既有捕捉中的兩處程式指紋。指紋值寫在程式內。磁碟程式位元組不能替代已載入程式指紋。

Win32 部分只要求 `PROCESS_QUERY_INFORMATION | PROCESS_VM_READ`。它按 [VirtualQueryEx](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualqueryex) 查詢頁面，再使用 [ReadProcessMemory](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-readprocessmemory) 讀取；要求 committed、可讀且沒有 guard 的區域，函式前綴還要求可執行的 image 區域。權限不足、短讀取、空指標、版本不符或模組變動都直接停止，不提升權限、不重試繞過限制。

指標欄位會重讀。欄位改變時輸出 `observed_fields_unchanged_on_reread: false` 並列出變動項；這種輸出不能當作一致快照。即使重讀相同，也無法排除中途變動後復原，因此所有輸出仍標示 `atomic_snapshot: false`。模組列表、磁碟檔案與已載入程式指紋在結尾再核對一次。

## 離線檢查

使用 64-bit Python，無第三方依賴。在 HD2 工作區根目錄執行：

```powershell
python -B five_player_feasibility_20260927/tools/interface_probe.py --plan
python -B -m unittest discover -s five_player_feasibility_20260927/tools -p test_interface_probe.py -v
```

`--plan` 及匯入模組均不開啟程序。測試注入合成記憶體讀取器，驗證固定指標路徑、null/非模組位址拒絕、欄位及程式短讀取、重讀變動、模組結尾裁切、PE 身分及程式指紋失配。**mock 通過只證明這些離線邏輯，不證明 Windows adapter、GameGuard 相容性或遊戲行為。**

## 擷取操作形式與本次範圍

使用者同意的這一次本機唯讀觀測已完成。以下保留操作形式供檢閱；未授權持續觀測或重複擷取。操作需要本人手動啟動的遊戲及其 PID；工具不啟動、暫停、注入或修改遊戲，也不會自動加入任何房間。單一帳號即可提供此介面資料，仍不能取代五至八人同場測試。

```text
python -B five_player_feasibility_20260927/tools/interface_probe.py --capture --pid <明確的遊戲PID> --output <尚不存在的JSON路徑>
```

本次取得 API `+0x30/+0x18` 目標為 EXE RVA `0x3494b0`、API `+0xf8/+0xa0` 目標為 EXE RVA `0x8c6730`，設定 `+0x20` 為零。下一步是離線分析已取得的函式前綴與所屬模組，確定還需哪些實作資料；不能由擷取成功推論擴容成功。程式前綴可能僅是跳板，本工具不自動追蹤分支或更多指標。
