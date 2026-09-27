# 已審查、待授權：handle wrapper 的單一直接 callee 擷取

**本工具已完成離線準備、合成驗證與獨立審查，尚未取得本次執行授權，也未執行活程序擷取。** 先前三次單次擷取均已完成。這份計畫要由使用者另行授權，才可對手動開啟的遊戲執行一次。

## 來源與目的

第三次保存檔 [spawn_interface_live_20260927_1.json](../spawn_interface_live_20260927_1.json) 的 SHA-256 為：

`44773c271226df2df3a93991421287cee71ea7971cbad877ed5a70275dff798a`

其函式指標定位到 EXE RVA `0x30FF50`。從該已知入口解碼的正常路徑包含 9 條指令、34 bytes，於 `0x30FF71` 返回。當中的 **`0x30FF66` 是直接 `call 0x1AE380`**，並非依字串或未知指標猜測的下一跳。本工具只準備讀取這個已知 callee 的固定前綴。

Caller pin 覆蓋 EXE `[0x30FF50, 0x30FF72)`，其 34 bytes SHA-256 為：

`387a2d5d4cd5499df56722eb328d0fe917218678c625847078962f83c6e4ffa9`

來源已由完整保存 JSON 的 SHA、4 KiB 前綴 SHA、9 條指令邊界及 `E8 rel32` 目的位址核對。Wrapper 將原始 64-bit 資源 hash 改為地址參數，並讀取下游回傳指標指向的一個 dword。這能定位 handle 相關資料流；尚未證明下游是玩家專用分配器或其容量已支援八人。

## 固定範圍與精確預算

| 項目 | 讀取安排 | 總 bytes |
| --- | --- | ---: |
| EXE `0x1AE380` 前綴 | 4,096 bytes，各讀兩次 | 8,192 |
| EXE wrapper caller pin | 34 bytes，前後各一次 | 68 |
| 兩個載入映像 PE header | 2 × 4,096 bytes，前後各一次 | 16,384 |
| 原有 game.dll 程式 pins | 76 + 36 bytes，前後各一次 | 224 |
| **總計及本工具硬上限** | | **24,868** |

原有 game.dll pins 是 `0x108C18F`（76 bytes）及 `0x4EDAA4`（36 bytes）。另外前後核對 EXE／DLL 的磁碟完整 SHA、程序路徑、模組清單、載入 PE 身分及大小。磁碟檔案 hashing 和模組 metadata 查詢不計入上表的 `ReadProcessMemory` bytes。

只允許 build `25480438` 的已固定 EXE／DLL 檔案 SHA。Caller 與目標完整範圍須屬於同一個已驗證的 EXE，不能截短越界讀取。沿用未修改的 `interface_probe.py` Windows adapter，要求可讀、可執行的 `MEM_IMAGE` 頁面。外層精確預算把原 adapter 上限縮小為 **24,868 bytes**。

任何前後身分變化、caller 指紋不符、callee 重讀不同、短讀、範圍越界、地址溢位或頁面條件不符，都會停止，且不保存成功結果。工具只讀固定 RVA，不讀取新發現的指標、跳板或下游呼叫。沒有程序搜尋、啟動、關閉、暫停、遊戲函式呼叫、記憶體／遊戲檔寫入、提權或重試。

## 離線操作

不帶參數或使用 `--plan` 只輸出計畫；不會開啟程序。

```powershell
python -B five_player_feasibility_20260927/tools/spawn_callee_probe.py --plan
python -B -m unittest discover -s five_player_feasibility_20260927/tools -p test_spawn_callee_probe.py -v
```

測試使用保存的第三次 JSON 及合成 adapter，覆蓋 caller／callee 的來源與指令邊界、精確讀取序列、短讀、程式及 caller 變化、載入 PE／路徑／模組／磁碟身分變化、hash／名稱／映像大小及範圍錯誤、預算、離線模式不開程序，以及失敗不建立輸出且關閉合成 handle。合成交易用相同位置／長度的合成 game pins；不假稱合成 bytes 驗證過實際遊戲程式。

準備階段的 **16 項離線測試已全部通過**。主代理另行閱讀完整工具與測試，核對沿用 adapter 未修改、固定 RVA 與 34-byte caller pin、12 筆成功讀取序列及精確硬預算，並重新執行全部 16 項測試通過。此獨立審查只使用保存檔與合成資料，沒有查詢或開啟遊戲程序，也不構成本次擷取授權。

## 另行授權後才可使用的形式

```text
python -B five_player_feasibility_20260927/tools/spawn_callee_probe.py --capture --pid <明確遊戲PID> --output <尚不存在的JSON路徑>
```

輸出只能建立新檔，不能覆寫。成功結果會保存 code bytes、重讀 SHA、已核對的映像身分、工具 SHA 和精確讀取量；`atomic_snapshot=false`、`eight_player_verified=false`。

4 KiB 是擷取上限，不是完整函式邊界；內容可能只是一部分、跳板或包含鄰接程式／資料。即使重讀相同，也不能排除中間變動、卸載重載或地址重用。此工具沒有執行下游函式、觀察 handle 成功返回、角色生成或五／八人任務。
