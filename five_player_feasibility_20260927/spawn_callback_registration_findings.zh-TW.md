# 找到 roster 插入的靜態 callback 登錄：component index 239

## 新結果

**已找到實際寫入三張資源派發 callback 表的初始化函式，並將四槽 roster 插入函式綁定到 component index 239。** 先前「找不到 `0x540920` 的函式指標引用」的結果，受搜尋工具只驗證有 unwind 的位置所限；本次定位到有直接呼叫證明、但本身沒有 unwind 項目的大型 leaf 初始化函式，補上這個盲點。

目前確定的是靜態初始化與分派索引對應。沒有觀察遊戲是否執行某一次回呼，也沒有用此结果代替資源雜湊→索引清單的獨立證據。全部分析只讀原固定 game.dll 捕捉，未讀活程序、安裝 Mod 或修改遊戲。

## 1. 為何先前精確位移掃描只看到讀者

扩大搜尋 `0xF0C000 .. 0xF0DFFF` 的位移後，出現大量每 8 bytes 間隔、卻被標為「不在 unwind 中」的匹配。其實際位置在 `0x556D90 .. 0x55E1E2`。

`0x568239` 是已由 unwind fragment 驗證的 `call 0x556D90`，確立真正入口。從該入口到 `0x55E1E2` 的 `ret` 完整順序解碼結果是：

- **29,779 bytes、4,255 條指令。**
- **2,127 組 `lea rax,[rip+函式位址]` → `mov [rcx+固定偏移],rax`**，最後接一條 `ret`。
- 全程沒有分支、呼叫、RCX 修改或重複目的位址；不是從零散匹配位元組開始猜測指令。
- 完整區段 SHA256：`22c57829a02419f7e8689a6e2ca501c353fa5362904c6b49e108689d842c91b2`。

這個無 unwind leaf 解釋了為何舊 `field_refs.py` 與引用搜尋沒有列出這些寫入；它不表示程式沒有寫入表。

## 2. 表基底精確等於原 context +0x40

已固定以下建構鏈：

```text
FDA190 entry context
  FDA1A4: RBX = context
  FDA356: global346BF98 = context
  FDA352: RCX = context + 0x40
  FDA375: call 551B60
    551B7D: call 568230（入口 RCX 未改）
      568239: call 556D90（入口 RCX 未改）
        [RCX + tableOffset] = callback
```

`0xFDC140` 的派發路徑則在 `0xFDC165` 保存入口 context，於 `0xFDC250` 再形成 `context+0x40` 傳入 `0x581320`。因此本頁表位移均相對於 **component owner = 原 context+0x40**；不能再對表位移自行加減未知基底。

`0x551B60` 亦在這個 owner 的 `+0xEA0818` 初始化 roster；`0x568EC8/0x568ECF` 將該子物件發布到 `global 0x3326468`。表中的插入 callback 從同一全域取 roster，物件身分可直接連回。

## 3. 三個既有派發點的 index 239 對應

`239*8 = 0x778`。

| 已確認讀者的表起點 | index 239 的寫入位置 | LEA → store 指令 | 登錄 callback 與行為 |
| --- | --- | --- | --- |
| `+0xF0C110` | `+0xF0C888` | `0x55BFD0 → 0x55BFD7` | **`0x540920`**：四槽 roster 插入，含 `count+1 <=4` 檢查，失敗寫零位址。 |
| `+0xF0CB30` | `+0xF0D2A8` | `0x55BFEC → 0x55BFF3` | **`0x540AE0`**：重排參數並 `call 0x60C640`。後者用途不在本頁擴張推斷。 |
| `+0xF0D550` | `+0xF0DCC8` | `0x55BFFA → 0x55C001` | **`0x540B10`**：`mov r8,rdx; mov rdx,rcx; jmp 0x6054F0`。 |

相應間接呼叫仍是 `0x581421`、`0x58152F`、`0x581A4E`。這使以下說法具體成立：**如果資源分派清單選中 index 239，且表保留這段初始化結果，第一張表會選到已確認的四槽 roster 插入 `0x540920`。**

`0x540B10` 自己也沒有 unwind，但其被寫入已驗證 callback 表，建立該入口的獨立來源；本次從該入口完整解碼 11 bytes 至 tail jump，沒有把任意 offset 當作函式。

## 4. 同一索引的其他登錄

完整 initializer 還有同一欄位群的寫入：

| owner 相對目的位移 | callback |
| --- | --- |
| `+0xF0BE68` | `0x540850`，另一個已確認的四槽 roster 插入實作 |
| `+0xF0F108` | `0x540A40`，先前已分析的 roster 移除實作 |
| `+0xF0E6E8` | `0x540B20` |
| `+0xF0FB28` | `0x540B30` |
| `+0xF10548` | `0x540B50` |
| `+0xF10F68` | `0x540B40` |
| `+0xF11988` | `0x540B60` |

這些寫入也固定在證據中，但本頁沒有將尚未追查的表讀者命名為某種生命週期。尤其 `0xF0B6F0` 起點的第一組不能僅憑排序稱為某個確定執行階段。

另兩個曾分析的 helper `0x60CA80/0x60CBA0` **不是這個 initializer 的直接 LEA 目標**；它沒有推翻它們可能由其他程式呼叫，只確定這張表實際寫的是 inline 版本 `0x540850/0x540920`。

## 對八人 Mod 的具體影響

先前只知道某幾個插入函式有四筆限制，現在找到其中一個進入資源分派的**具體索引與實際 callback**。這使擴容研究可以針對真正登錄的 `0x540920` 和後續 phase 設計修改，而非假設沒有 caller 的 helper 就是唯一入口。

仍需保留的界限：

- 資源 `player` 或 `avatar` 究竟包含 index 239，必須以各自的資源 metadata 清單證明；本頁不以 callback 的內容倒推出清單。
- 本次沒有捕捉 writable callback table，所以未排除初始化後被改寫或不同生命週期路徑。
- callback 定位本身不提供八筆 roster 儲存空間，也沒有驗證八人加入、角色生成、同步或結算。

## 重播產物

- **`spawn_callback_registration_evidence_v2.json`**：主證據，增加原 context 發布到 `global346BF98` 的核對；包含 59 個 unwind 指令位置、index 239 的 10 組精確 LEA／store、11-byte tail wrapper 和完整 initializer 指紋。
- `spawn_callback_registration_replay.py`：驗固定來源 SHA，驗 caller 的 unwind 邊界，再完整解碼無 unwind leaf 並逐組檢查整個初始化形狀，重算所有表格地址。
- `spawn_callback_registration_pairs.json`：全部 2,127 組 initializer LEA／store 的探索輸出。
- `spawn_callback_registration_entry_xrefs.json`：`0x568239 → 0x556D90` 入口證明。
- `spawn_callback_registration_owner_xrefs.json`、`spawn_callback_registration_constructor_xrefs.json`：建構呼叫鏈。
- `spawn_callback_registration_fields.json`：擴大位移搜尋，包括先前被省略的無 unwind 原始匹配計數。

```powershell
& 'C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe' `
  .\five_player_feasibility_20260927\spawn_callback_registration_replay.py `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output .\five_player_feasibility_20260927\spawn_callback_registration_replayed_new.json
```
