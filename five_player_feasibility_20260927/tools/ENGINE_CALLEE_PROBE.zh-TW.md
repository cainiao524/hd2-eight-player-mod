# 第二階段：四個 EXE 下游函式的限定唯讀擷取

先前使用者同意的單次擷取結果為 `interface_probe_live_20260927_1.json`。使用者其後另行同意本工具的四個固定函式擷取；已於 2026-09-27 香港時間 **12:15:19** 完成，保存於 [engine_callee_live_20260927_1.json](../engine_callee_live_20260927_1.json)。實際讀取 **50,400 bytes**，四段重讀相同，版本與 caller 指紋檢查通過。它補上了已定位但磁碟無法還原的四段程式，不是八人 Mod。

保存 JSON SHA-256：`157ddf9f9f9c04265dbc80109441af7090fcf78316e8642781857668348f129a`。本次授權擷取已完成；工具不會持續觀測，也沒有另行讀取更多函式。

## 為什麼需要這些資料

已保存的兩個平台 API 入口各包含兩個直接呼叫。`+0x30/+0x18` 路徑把設定值作為下游參數；`+0xf8/+0xa0` 路徑會把「設定值加四」寫入物件並傳給下游。現在還不能判定這些欄位的業務意義、深層容量檢查或實際服務要求。前一個入口的磁碟程式與保存的載入內容不同，後一個及其下游沒有對應磁碟 raw bytes，所以必須取得載入程式，才能繼續可靠的分析。

## 固定範圍

| EXE RVA | 已保存的直接呼叫位置 | 本次讀取長度 |
|---|---|---:|
| `0x4acde0` | `0x34952a` | 4,096 bytes |
| `0x349110` | `0x34953c` | 4,096 bytes |
| `0x8ccfa0` | `0x8c67ad` | 4,096 bytes |
| `0x8e1370` | `0x8c67c2` | 4,096 bytes |

每段只從表列位置讀取，然後重讀一次比較。工具不解析新位址、不繼續追指標或分支。4 KiB 是擷取範圍而非函式邊界；可能包含後續函式或資料，也可能不足以涵蓋完整函式，分析時需另行核對控制流程。

另有前後版本檢查：磁碟 EXE／DLL 完整 SHA-256、載入 PE header、原先兩處 game.dll 程式指紋，以及前次保存的兩個 EXE 入口各 256 bytes 的 SHA-256。預計 `ReadProcessMemory` 總量 **50,400 bytes**，硬上限 **65,536 bytes**。欄位或程式穩定性無法提升為原子快照；輸出明示 `atomic_snapshot: false`。未包含玩家名單、帳號資料、heap 物件或服務回應。

沿用 `interface_probe.py` 中經審查的 Windows adapter，只要求查詢與讀取權限。沒有遊戲函式呼叫、記憶體寫入、程序暫停、權限提升、網路上傳或自動重試。需要手動開啟的遊戲及明確 PID；版本／頁面／短讀取檢查失敗時停止。輸出只能寫入尚不存在的新檔案。

## 已完成的離線檢查

```powershell
python -B five_player_feasibility_20260927/tools/engine_callee_probe.py --plan
python -B -m unittest discover -s five_player_feasibility_20260927/tools -p test_engine_callee_probe.py -v
```

6 項測試涵蓋：用原始保存位元組驗證四個 direct-call 目標、只讀四段並各讀兩次、程式變動保存兩版且不標穩定、短讀取拒絕、模組越界拒絕，以及已保存 caller 指紋不符時停止。所有測試都只讀保存檔案或合成資料；匯入工具及 `--plan` 不會開啟程序。

## 本次使用的操作形式

```text
python -B five_player_feasibility_20260927/tools/engine_callee_probe.py --capture --pid <明確遊戲PID> --output <尚不存在的JSON路徑>
```

即使觀測成功，也只能供下一步離線反組譯。是否能建立八人房、生成第五名玩家、同步戰鬥並完成任務，需要各自的實作與驗證。

已保存的四段正常控制流程由 [exe_capture_cfg.py](exe_capture_cfg.py) 離線整理，結果在 [engine_callee_cfg_20260927.json](../engine_callee_cfg_20260927.json)。它從已知 direct-call 入口追區內分支，遇到其中一個 `ret` 後仍處理其他分支；不追呼叫、例外或間接跳躍。三項合成控制流程檢查確認多個 return 路徑、缺失目標回報，以及跳入指令中間的拒絕。
