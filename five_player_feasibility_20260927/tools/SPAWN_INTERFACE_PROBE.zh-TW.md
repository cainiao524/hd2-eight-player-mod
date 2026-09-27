# 已完成一次：名單相關 handle 產生介面的限定唯讀擷取

**使用者已另行同意本次單一介面的唯讀擷取，並於香港時間 2026-09-27 12:49:36 成功完成一次。** 本次及前兩次授權均已使用完畢。後續只分析保存結果；再次活程序擷取需新的明確授權。執行 `--plan` 或不帶參數只列出計畫，不會開啟程序。

本次讀取總量 **24,966 bytes**，定位目標為 `helldivers2.exe+0x30FF50`。九條指令的轉接入口呼叫 `EXE+0x1AE380`；未追讀範圍外的下游。保存 JSON、SHA、資料流及局限見 [本次分析](../spawn_interface_findings.zh-TW.md) 與 [獨立核對](../spawn_interface_independent_review.zh-TW.md)。

## 要補上的資料

已保存的 `game.dll` 程式顯示，`0xAC9C19` 的間接呼叫回傳 handle，之後將 handle 寫回玩家名單。目標位址只能由執行期的四個指標欄位取得：

```text
game.dll + 0x3326308  → api
api + 0xC0           → object
object + 0           → vtable
vtable + 0x18        → function
```

這裡包含 **object 首個指標的額外解參考**，不是 `api+C0+18` 的直接函式表槽。固定 caller 指紋涵蓋 `0xAC9BE9` 至 `0xAC9C1C`（結尾不含），共 **51 bytes**；其中 `0xAC9C19` 的 `call r9` 是三個 bytes。指紋已依先前保存且 SHA-256 固定的程式資料、unwind 起點及完整指令邊界核對。

Caller 的資源參數是 `0xB04D927AFB137B9B`。目前離線字串 hash 對照指向 `content/entities/dummy`；這不能單憑名稱視為玩家角色資產。本工具的目的限定為解析「名單相關 handle 產生介面」，沒有假定它就是玩家專用分配器。

## 固定讀取範圍

| 項目 | 每次／數量 | 包含重讀的總 bytes |
| --- | ---: | ---: |
| 上列四個指標欄位 | 4 × 8，各讀兩次 | 64 |
| 最終函式入口前綴 | 4,096，讀兩次 | 8,192 |
| 兩個載入映像的 PE header | 2 × 4,096，前後各一次 | 16,384 |
| 原有 game.dll 兩處程式指紋 | 76 + 36，前後各一次 | 224 |
| 本次 caller 指紋 | 51，前後各一次 | 102 |
| **總計及本工具硬上限** | | **24,966** |

原有程式指紋位置為 `game.dll+0x108C18F`（76 bytes）及 `game.dll+0x4EDAA4`（36 bytes）。另會前後核對磁碟 EXE／DLL 完整 SHA-256、載入映像大小與身分、程序路徑及模組清單；磁碟檔案讀取與模組 metadata 查詢不計入上表的 `ReadProcessMemory` bytes。

最終函式的完整 4 KiB 範圍必須落在固定 SHA-256 已通過的 **helldivers2.exe 或 game.dll** 其中之一，且 Windows 查詢必須確認每頁是可執行的 `MEM_IMAGE`。其他 DLL、heap 程式或越界目標一律停止。工具只重读原先四個欄位的原位址；任一欄位或程式重讀不同時停止，不追隨變更後指標。指標空值、非使用者位址、加法／範圍越界、短讀、版本變更、頁面條件不符也都停止。

沿用已審查的 `interface_probe.py` Windows adapter，沒有修改該檔；程序權限只有 `QUERY_INFORMATION | VM_READ`。外層另把 adapter 的 65,536-byte 上限縮小為本次精確的 **24,966 bytes**。不會啟動或關閉遊戲、寫入遊戲記憶體或安裝檔、呼叫遊戲函式、暫停程序、提權、重試、解析跳板或繼續讀取新發現的 calls。欄位以外的物件內容、遊戲設定、玩家資料及服務回應不在範圍內。

## 離線檢查

```powershell
python -B five_player_feasibility_20260927/tools/spawn_interface_probe.py --plan
python -B -m unittest discover -s five_player_feasibility_20260927/tools -p test_spawn_interface_probe.py -v
```

合成記憶體及已保存證據的測試涵蓋固定讀取序列、四個指標各自變更、程式變更、短讀、未擁有目標、映像尾端越界、指標加法／程式範圍溢位、未通過 SHA 的映像、第三個映像、game.dll 固定位置越界、精確預算、caller 位元組、caller 變更，以及預設／明確 `--plan` 不開程序。這些測試無法代替真實程序上的頁面或成功擷取驗證。

## 取得另外授權後才可使用的形式

```text
python -B five_player_feasibility_20260927/tools/spawn_interface_probe.py --capture --pid <明確遊戲PID> --output <尚不存在的JSON路徑>
```

輸出只能建立新檔，不能覆寫舊結果。成功擷取也只證明當時讀到的指標及前綴；相同重讀不是原子快照，無法排除中間改變或位址重用。4 KiB 可能不足以包含整個函式，也可能含其他函式／資料。沒有執行該呼叫、取得實際回傳 handle、證明角色成功生成或验证第五／第八名玩家。

## 獨立審查（2026-09-27）

主代理已閱讀完整工具、測試及沿用的 Windows adapter，重新執行 17 項離線測試，全部通過。另直接從原始固定捕捉讀出 caller 的 51 bytes，核對 SHA-256 `6c78736c1f150bd2f9e600a811d71464658f0dd8093768f8f4cfb60a073d8536` 及九條指令邊界；確認四個指標讀取步驟包含物件首指標的解參考。讀取總量、兩個固定映像限制、變動時停止與關閉 handle 的流程均已檢查。此審查沒有開啟遊戲程序，不構成本次擷取授權。
