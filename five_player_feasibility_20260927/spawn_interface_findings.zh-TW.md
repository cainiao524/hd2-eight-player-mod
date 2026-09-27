# 第三次唯讀擷取：名單 handle 介面已定位

日期：2026-09-27。使用者另行同意本次限定擷取後，先查得手動啟動的 `helldivers2.exe` PID `39964`，再執行一次既有工具。香港時間 **12:49:36** 成功保存結果。本次授權已使用完畢，其後只分析保存檔案。

## 保存來源與核對

| 項目 | 結果 |
|---|---|
| 保存 JSON | [spawn_interface_live_20260927_1.json](spawn_interface_live_20260927_1.json) |
| JSON SHA-256 | `44773c271226df2df3a93991421287cee71ea7971cbad877ed5a70275dff798a` |
| 遊戲 build | `25480438`，兩個磁碟映像 SHA 與前後版本檢查通過 |
| 程序記憶體讀取總量 | **24,966 bytes**，與預定硬上限相等 |
| 目標 | `helldivers2.exe` RVA **`0x30FF50`** |
| 前綴大小及 SHA-256 | 4,096 bytes；`484f5437b325ff273041e496b4f609d393ed24a4af38b63cce5c6f63d706b04a` |
| 重讀 | 四個原欄位及程式前綴相同；並非原子快照 |

固定指標鏈：

```text
game.dll+0x3326308 → api
api+0xC0          → object
object+0          → table
table+0x18        → EXE+0x30FF50
```

保存資料的重播程式 [spawn_interface_replay.py](spawn_interface_replay.py) 核對 JSON 完整 SHA、欄位 bytes 與指標關係、固定版本元資料、讀取分項及程式前綴雜湊。其 [分析輸出](spawn_interface_evidence.json) 與 [獨立審查](spawn_interface_independent_review.zh-TW.md) 一致。

JSON 不包含 PE／caller 檢查的原始 bytes 或四指標的第二份原始 bytes。這些項目的成功狀態來自已審工具在輸出前的檢查；後續審查可核對保存元資料及工具身分，不能重現當時頁面權限或排除兩次讀取之間的變化。

## 九條指令完成參數轉接

由已定位入口追蹤正常控制流程，共 **9 條指令、34 bytes**：

```asm
30FF50  sub rsp, 0x28
30FF54  mov qword ptr [rsp + 0x38], rdx
30FF59  mov r9, r8
30FF5C  lea r8, [rsp + 0x38]
30FF61  lea rdx, [rsp + 0x30]
30FF66  call 0x1AE380
30FF6B  mov eax, dword ptr [rax]
30FF6D  add rsp, 0x28
30FF71  ret
```

以轉接入口的暫存器值為準，呼叫 `0x1AE380` 時：

| 下游參數／返回 | 已確定的資料流 |
|---|---|
| `RCX` | 保留入口值；原 game.dll caller 從另一來源傳入 world/context 值，不能視為上述介面 object 的 `this`。 |
| `RDX` | 指向入口 `RSP+8` 的暫存空間。其作為輸出記錄的用途符合形狀，但下游尚未解析。 |
| `R8` | 指向入口 `RSP+0x10`，該處存有入口 `RDX` 的完整 64-bit 值，即此 caller 的 dummy 資源 hash。 |
| `R9` | 保留入口 `R8`。 |
| wrapper 的 `EAX` | 下游返回後讀取 `DWORD [RAX]`，再返回給 game.dll；不是直接返回下游的指標。 |

這段沒有條件分支，也沒有比較四或八。`CFG unresolved=[]` 只表示所分析正常跳轉沒有缺口；**唯一的 call 目標 `0x1AE380` 在保存範圍外，仍未解析**。4 KiB 中的其他 bytes 不因相鄰便屬於同一函式。

### 下游的既有資料可用性

[離線覆蓋核對](spawn_callee_availability.zh-TW.md)確認，三份固定 EXE 捕捉的七個窗口都不含 `0x1AE380`。其磁碟位置可換算為 file offset `0x1AD980`，但同 section 的已知入口 `0x30FF50` 在磁碟和載入後的首 byte 分別為 `8B`、`48`，完整 4 KiB 也不相同。因此磁碟 raw backing 不能代替經核對的載入後程式；目前未將下游磁碟 bytes 解釋成實際函式。這並未直接比較下游的磁碟／記憶體內容，因為後者尚未保存。

## 與八人 Mod 的關係

本次把「未知間接引擎介面」縮小為具體轉接入口及下一個直接呼叫目標。配合先前 [資源分派分析](spawn_resource_identity_findings.zh-TW.md)，可描述如下靜態資料流：

```text
game.dll caller：傳入 dummy hash
  → EXE+30FF50：把 hash 改為按地址傳入
  → EXE+1AE380：實作尚未保存
  → 讀取返回指標指向的 32-bit 值
  → game.dll：關聯 player／avatar hash，進入元件回呼分派
  → 已定位的名單 handle／狀態寫回
```

這沒有觀察介面被實際呼叫、有效 handle 返回、實體建立成功或第五人加入。也不能排除更深層實作中的容量限制。已確認的原生名單、客戶端、房主、平台成員陣列、tag `0x73` 資料及裝備畫面的四槽布局仍需完整擴容。

目前沒有可交付的八人 Mod；本次產物是可重播的介面定位證據。

## 離線重播

在工作區根目錄執行，输出檔名必須尚未存在：

```powershell
python -B five_player_feasibility_20260927/spawn_interface_replay.py --capture five_player_feasibility_20260927/spawn_interface_live_20260927_1.json --output spawn-interface-replay-check.json
```

此命令只讀保存檔案，不開啟遊戲程序。
