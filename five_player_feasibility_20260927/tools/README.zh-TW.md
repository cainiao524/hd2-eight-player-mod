# 八人原生布局研究工具

這裡的離線掃描工具用於列出八人擴容必須核對的原生存取位置。`layout_inventory.py`、`field_refs.py` 讀取既有的遊戲程式捕捉，輸出分析 JSON；沒有修改或載入遊戲的功能，也不是八人 Mod 安裝器。

另新增的 `interface_probe.py` 用於限定唯讀程序觀測，與上述離線掃描工具的執行範圍不同。其預設行為只顯示計畫，實際程序讀取需 `--capture` 與明確 PID。本輪先完成 mock 測試，其後經使用者同意完成一次限定擷取；範圍、結果及限制見 [INTERFACE_PROBE.zh-TW.md](INTERFACE_PROBE.zh-TW.md)。

`engine_callee_probe.py` 在另一次明確授權下，完成四個指定 EXE 函式各 4 KiB 的擷取與重讀，總 50,400 bytes，見 [第二階段工具說明](ENGINE_CALLEE_PROBE.zh-TW.md)。兩次擷取都已結束。`exe_capture_cfg.py` 只讀第二次保存 JSON，追蹤區內正常控制流程，不會開啟程序。

`spawn_interface_probe.py` 經第三次明確授權，完成四個指標及單一 4 KiB 前綴的限定擷取，含檢查與重讀共 **24,966 bytes**；目標為 `EXE+0x30FF50`。見 [第三階段工具說明](SPAWN_INTERFACE_PROBE.zh-TW.md)。三次擷取均已結束；[spawn_interface_replay.py](../spawn_interface_replay.py) 只重播第三份保存 JSON，已核對九條入口指令及範圍外的直接下一跳，沒有繼續存取活程序。

另備 `spawn_callee_probe.py`，計畫限定讀取上述已知下一跳 `EXE+0x1AE380` 的 4 KiB，包含重讀與前後檢查共 **24,868 bytes**。工具及 16 項離線測試已獨立審查；已向使用者提出新的一次擷取授權請求，尚未執行。範圍見 [單一下游工具說明](SPAWN_CALLEE_PROBE.zh-TW.md)。

已在本工作區以 Python 與 Capstone 5.0.7 執行。共用讀取器為 `research_handoff_20260927/indirect/inspect_capture.py`，它會核對 `capture-report.json`、`captured-data.bin` 的完整 SHA-256，並以已捕捉的 unwind 表核對指令邊界。此工具只適用已固定的 build `25480438` 捕捉；不能將其 RVA 套到其他版本。

從 HD2 工作區根目錄執行，輸出必須選尚不存在的檔名：

```powershell
$taskCapturePath = 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438'
python -B five_player_feasibility_20260927/tools/layout_inventory.py --evidence $taskCapturePath --output host-inventory-replay.json
python -B five_player_feasibility_20260927/tools/field_refs.py --evidence $taskCapturePath --offset 0x159b0 --offset 0x162c8 --output host-owner-replay.json
python -B five_player_feasibility_20260927/tools/field_refs.py --evidence $taskCapturePath --range 0x159b0 0x162c8 --output host-region-replay.json
```

`layout_inventory.py` 以 `HostSynchronizer` 字串引用找出候選函式，保存各 unwind 片段的指紋、相關字串、固定偏移與常數的使用位置，以及直接呼叫。現有結果為 84 個有效字串引用、40 個候選根函式，所有列出的片段都完整反組譯。

`field_refs.py` 先找 disp32 位元組候選，再確認它確實位於有效指令的記憶體位移欄位。`--range` 的結尾不包含，且兩端必須在同一個 64 KiB 位移區段。範圍中的同一偏移可能屬於完全不同的物件，必須檢查基底暫存器的來源；例如 `+0x159b0` 的數字相同，並不自動表示它是房主子物件。精確掃描與範圍掃描對已知 `0x159b0`、`0x162c8` 引用的輸出已比對一致。

這些清單不涵蓋所有計算出來的位址、沒有 unwind 記錄的 leaf 函式、其他模組或執行期分派。它們不能直接當成要替換的指令清單，也不能證明第五人或第八人已成功加入。
