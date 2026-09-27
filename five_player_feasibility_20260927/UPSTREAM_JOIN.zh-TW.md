# 加入請求上游路徑：同版離線補充

本頁只描述 Steam build `25480438` 既有捕捉中的靜態程式碼。原捕捉 `capture-report.json` SHA-256 為 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`；`captured-data.bin` SHA-256 為 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。讀取器會先完整核對兩者，再使用 unwind fragment 驗證指令邊界。未啟動遊戲或修改安裝檔。

## 通往房主加入處理的入口

| RVA | 固定 bytes | 已觀察到的關係 |
|---|---|---|
| `0xB933B5` | `81bcc500670000ec000000` | root `0xB93350` 在遍歷一組記錄時，檢查已註冊物件的 tag `0xEC`。 |
| `0xB93406` | `e865884f00` | 同一 root 直接呼叫加入處理函式 `0x108BC70`。 |
| `0xBA8DC5` | `81bcc500670000ec000000` | root `0xBA8CC0` 也檢查該 tag `0xEC`。 |
| `0xBA8E13` | `e8582e4e00` | 同一 root 直接呼叫 `0x108BC70`。 |
| `0x214C6A0` | `c08c5d15f87f0000` | captured readonly 中的絕對 VA，等於 capture base `0x7FF814A30000` + `0xBA8CC0`。它位於從 `0x214C2E0` 開始的連續 code pointer 區段；該區段 consumer 未確認。 |

`0xBA8CC0` 還在 `0xBA8CF7` 從輸入 `[RDX+0x18]` 讀計數，並在 `0xBA8D30–0xBA8D54` 依該計數將 qword 複製到固定堆疊佈局，然後才呼叫 `0x108BC70`。這是上游資料佈局需要檢查的證據；未找到該處顯式 `count <= 4` 判斷，不能稱它為另一個已證的四人拒絕點。

後續的 `host_event_registration_disasm.json` 已確認 `0xEC` 是 host pointer 加入 registry 時的 tag；這裡不把它稱為網路封包或事件編號。

補充修正：後續[初始化及註冊函式反組譯](host_event_registration_disasm.json)顯示 `0xB2AFB0` 將房主物件指標與 `0xEC` 標籤加入多個回呼登錄表，其中一表的成員位址與上述兩條加入路徑吻合。因此 `0xEC` 應稱註冊物件／listener 的種類標籤，不能當成已知的網路事件編號。

## 房間建立與服務邊界

本頁的加入入口追查沒有獨立定位建立呼叫；後續沿平台子系統已找到建立／重建呼叫候選及明確的四人成員列舉，最新證據見[建立路徑補充](creation_path_findings.zh-TW.md)。實際介面函式與服務接受結果仍未確認。

同一 captured readonly 有 `/lobby`、`numLobbyMembers`、`numSessionMembers`、`lobby/memberCount` 等字串。這些字串在 captured code 有部分經邊界核對的 RIP xref，見 `lobby_string_xrefs.json` 與 `lobby_member_string_xrefs.json`。例如 `numLobbyMembers` 指向 root `0x1053F60` 與 `0x12CB190` 中的欄位處理；`/lobby` 指向 root `0x12CB190` 中的路徑格式化。這些資料本身不能確定房間建立時的最大人數、平台或服務的接受條件。後續另沿 `start_hosting` 找到建立呼叫，詳見 `creation_path_findings.zh-TW.md`。

此次掃描在 captured code 內只找到上述兩個對 `0x108BC70` 的直接 `CALL/JMP rel32`；對 root `0xB93350` 沒有找到直接呼叫或 captured absolute pointer。`0xBA8CC0` 的 pointer table 未找到可核對的 consumer。這是限定掃描方法與捕捉範圍內的負結果，不是完整呼叫圖：沒有 heap 或可寫全域資料、其他模組、執行期分派、任意地址算術、無 unwind leaf 函式，也沒有線上測試。

## 重播

以 `research_handoff_20260927/indirect/inspect_capture.py` 指向原 repo 的 `build/existing-code-evidence-25480438/`，分別使用 `--target 0x108bc70`、`--target 0xb93350 --target 0xba8cc0`、`--target 0x214c2e0 --target 0x214c6a0`。輸出須使用尚不存在的路徑。此目錄現有 `host_join_xrefs.json`、`host_join_caller_xrefs.json`、`host_join_table_xrefs.json` 保存結果及來源指紋。`lobby_string_xrefs.json` 與 `lobby_member_string_xrefs.json` 保存字串 xref。
