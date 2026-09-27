# 第三次單介面擷取：獨立離線審查

本審查只讀已保存 JSON、工具原始碼及舊固定捕捉。沒有開啟、查詢或讀取活遊戲程序，沒有修改主要報告或其他分析檔案。

## 保存結果的完整性

- 保存檔：[spawn_interface_live_20260927_1.json](spawn_interface_live_20260927_1.json)
- JSON SHA-256：`44773c271226df2df3a93991421287cee71ea7971cbad877ed5a70275dff798a`
- 擷取時間：`2026-09-27T04:49:36.086697+00:00`，即香港時間 12:49:36。
- Build `25480438`，紀錄的 PID `39964`。
- `memory_bytes_read = 24966`，與五個分項及工具的精確硬上限相等：`16384 + 224 + 102 + 64 + 8192`。
- 保存的工具／adapter SHA 與目前檔案相符；兩個 pinned image 的檔案 SHA、映像範圍及函式归屬檢查通過。
- Caller pin 元資料與經舊原始捕捉核對的 `0xAC9BE9`–`0xAC9C1C`、51-byte 指紋相符：`6c78736c1f150bd2f9e600a811d71464658f0dd8093768f8f4cfb60a073d8536`。

已逐一核對四筆 8-byte little-endian 指標樣本的 bytes、value 及位址關係：

| 欄位地址 | 保存的值 |
| --- | --- |
| `game.dll base + 0x3326308 = 0x7FFB389D6308` | `api = 0x7FF62AED8D80` |
| `api + 0xC0 = 0x7FF62AED8E40` | `object = 0x7FF62AED9A50` |
| `object + 0 = 0x7FF62AED9A50` | `vtable = 0x7FF62AED9A30` |
| `vtable + 0x18 = 0x7FF62AED9A48` | `function = 0x7FF628A1FF50` |

最終函式是 **`helldivers2.exe + 0x30FF50`**。保存前綴長度恰好 4,096 bytes，整段位於該 pinned image；SHA-256 與重讀摘要相同，均為 `484f5437b325ff273041e496b4f609d393ed24a4af38b63cce5c6f63d706b04a`。

JSON 沒有再次保存 PE header、caller 原始 bytes 或四欄位的第二份原始 bytes；因此此獨立審查能驗證它們的保存元資料與已審查工具一致，不能憑 JSON 重新獨立量測擷取當時的頁面權限或版本狀態。已審查工具只有在上述前後檢查及重讀比較都通過後才會保存成功結果。`atomic_snapshot=false` 及 `eight_player_verified=false` 均保留。

## 入口正常控制流程

以保存的函式指標為入口，用既有離線 CFG 解碼器追正常分支；本次入口依據是**已保存的四欄位指標鏈與舊 caller 的間接呼叫**，不是先前四函式擷取的 direct-call 入口依據。

從 `0x30FF50` 到 `0x30FF71` 的第一個正常 `ret`，共 **9 條指令、34 bytes**：

| EXE RVA | 保存指令 |
| --- | --- |
| `0x30FF50` | `sub rsp, 0x28` |
| `0x30FF54` | `mov qword ptr [rsp + 0x38], rdx` |
| `0x30FF59` | `mov r9, r8` |
| `0x30FF5C` | `lea r8, [rsp + 0x38]` |
| `0x30FF61` | `lea rdx, [rsp + 0x30]` |
| `0x30FF66` | `call 0x1AE380` |
| `0x30FF6B` | `mov eax, dword ptr [rax]` |
| `0x30FF6D` | `add rsp, 0x28` |
| `0x30FF71` | `ret` |

這條入口路徑没有條件跳轉或間接跳轉。唯一直接呼叫 `0x1AE380` 位於本次保存 window 外；本審查没有追讀它。解碼器回傳 `unresolved=[]` 只表示入口路徑沒有未處理的正常跳轉，**不代表下游呼叫已解析**。尾端大量 `int3`、鄰接函式與後續資料不属于已證明的入口正常路徑，不能將全部 4 KiB 當成此函式的實作。

## 參數與回傳值

依 Windows x64 暫存器傳參位置，這個短入口做以下轉接：

| 呼叫 `0x1AE380` 時的參數 | 來源 |
| --- | --- |
| `RCX` | 入口 `RCX`，此 wrapper 沒有改動它 |
| `RDX` | wrapper 調整 stack 後的 `[rsp+0x30]` 地址；wrapper 本身沒有先填入此位置 |
| `R8` | `[rsp+0x38]` 地址，該位置保存入口 `RDX` 的完整 64-bit 值 |
| `R9` | 入口 `R8` |

既有 `game.dll+0xAC9C19` caller 的入口 `RDX` 是 `0xB04D927AFB137B9B`，與 `content/entities/dummy` 字串 hash 相符；這次確認該值會以**指向 64-bit 值的地址**傳給下游。入口 `R8` 指向 caller 準備的資料，wrapper 原樣轉交地址，沒有在本次入口解碼中解析內容。

下游回傳 `RAX` 後，wrapper 讀取 `DWORD [RAX]` 並以 `EAX` 返回。它不是直接把下游 `RAX` 指標本身當成 handle 返回。`RDX` 指向的 stack 區可能是輸出／暫存用法，但未解析下游，不能僅依此轉接命名完整 C++ 簽名或確認隱藏回傳參數約定。

## 可下與不可下的結論

**已補上的邊界：** 先前名單相關 handle 呼叫目前已解析到 EXE 的實際入口，且具體下一跳是 `0x1AE380`。入口把資源 hash 轉成指標參數，並從下游回傳指標讀取一個 32-bit 值返回。

**仍未證明：**

- 這九條指令沒有玩家數或 4／8 容量檢查；這不能排除 `0x1AE380` 或其他深層流程的限制。
- `sub rsp, 0x28`、stack `+0x30/+0x38` 是 stack 布局常數，不是玩家槽位或玩家數。
- 目前沒有此呼叫的執行 trace、回傳值、成功建立實體結果或八人測試。
- 不能把這個短 wrapper 直接命名為玩家專用 allocator，也不能據此認定 `dummy`、avatar 或玩家配置已经完成。
- 下一個程式實作缺口為 **EXE+0x1AE380**；本次單介面擷取已結束，沒有授權繼續追讀該呼叫。
