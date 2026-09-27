# 平台大廳建立與四人成員列舉：固定版本離線補充

本頁只使用 Steam build `25480438` 的既有捕捉。`creation_path_replay.py` 會先以 `inspect_capture.Image` 核對 `capture-report.json` SHA-256 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5` 與 `captured-data.bin` SHA-256 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`，再按 unwind fragment 驗證每條 pin 的指令邊界。逐條 bytes、SHA-256、root 與限制保存在 `creation_path_evidence_v3.json`。沒有執行或修改遊戲。

## 建立呼叫的已見參數

`start_hosting` 所接的 root `0x1091980` 在 `0x10919CA` 從 writable global RVA `0x3326340` 讀一個指標。`0x10919D1–0x10919DE` 設定 `owner+0x1B90`：先取常數 `4`；若指標的 `+0x20` 欄位非零，改用該欄位。因此此值**不是已證永遠等於 4**，因該 writable global 的內容不在捕捉內。

此 root 先呼叫 `0x1091560` 初始化一組大廳屬性，再於 `0x1091A76` 呼叫 `0x10922C0` 建立一份配置資料。`0x1091A95` 從 runtime 平台介面取得 `+0xA0` 函式指標；`0x1091A9C–0x1091AA5` 將 `owner+0x1B90` **加 4** 後置於 `ECX`，連同角色旗標與配置資料呼叫該函式，並把返回的 handle 存在 `owner+0`。因而在 `global+0x20 == 0` 的分支中，該呼叫收到的第一個整數參數是 `8`。**函式指標目標和第一參數的 API 名稱／用途尚未解析**；這不能表述為後端 `MaxPlayers=8`，更不能證明八名真人能同場。

同一 `+0xA0` 呼叫亦出現在 platform lobby 更新 root `0x10937A0` 的 `0x1093A6A–0x1093A9B`，用相同的 `owner+0x1B90 + 4` 作第一參數，再儲存返回 handle。這是建立或重建路徑的第二個靜態證據；不能從兩次呼叫推斷服務端是否接受。

## 同一步驟還建立另一種平台 handle

在 `0x1091980` 中，`0x1091A31` 先呼叫 `0x1091800`，返回後才在條件成立時於 `0x1091AA5` 呼叫上述 `+0xA0` 函式。`0x1091800` 從同一個 writable global RVA `0x3326308` 的介面 `+0x30` 取另一個函式指標 `+0x18`。`0x1091845` 把 `owner+0x1B90` 放在 `EDX`、`0x1091874` 把 `owner+0x1B94` 放在 `ECX`，`0x109187A` 執行間接呼叫，返回 handle 存於 `owner+8`。`0x10919E4–0x1091A01` 顯示 `owner+0x1B94` 的零設定預設為 `0x2710`，發生碰撞時 `0x10918BC` 遞增並在 `0x10918E8` 重試。所以在零設定分支，這個**另一個間接呼叫的第二個整數參數**是 `4`，與 `+0xA0` 呼叫的首參數 `8` 屬不同資料流；目前仍不知道兩個 API 的名稱、語義或後端目標。

`0x1091800` 的第二條分支走另一個未解析介面 (`0x1091912–0x1091963`)：`0x1091930` 把首參數設為 `2`，`0x109193A–0x109193E` 取該介面 `+0x20` 函式指標並呼叫；`EDX` 仍保留 `0x1091845` 放入的 `owner+0x1B90`，所以零設定分支的第二個整數參數亦為 `4`。前述 `+0x18` 呼叫由 RVA `0x3326E40` 指標的 `+8` 旗標選擇。後續更新 root `0x10937A0` 亦在 `0x1094475` 與 `0x1094579` 呼叫 `0x1091800`。`+0xA0` 路徑另受 RVA `0x3326348` 指標的 `+0x28` 旗標控制。這些旗標與介面目標的運行時內容均不在捕捉中，因此**不能把任一數值直接等同完整房間容量**。

初始化屬性中的索引 `4` 在 `0x10915DA–0x10915E6` 被設為數值 `1`。captured readonly 的顯示名稱表 `0x21D61C0 + 4*8` 指向 `NumMembers`；建立配置函式 `0x10922C0` 實際使用另一個表 `0x2264260`，其索引 `4` 是數字字串 `"4"`。初始屬性索引 `3` 使用 host ID、索引 `4` 設 `1`、索引 `5` 設 `1`，與名稱表 `HostId`、`NumMembers`、`State` 的次序吻合。因此這是**初始成員數 metadata 的有力靜態對應**，送出的鍵仍是數字字串；它與 `owner+0x1B90+4` 的建立呼叫參數為不同資料流。

## 後續成員列舉明確以四人為上限

更新 root `0x10937A0` 從一個平台介面方法取得人數後，`0x1093C91` 與 `4` 比較；超過時 `0x1093C96` 把本機 `owner+0x1BB0` 設為 `4`。隨後迴圈逐索引取得成員，寫入 `owner+0x1B58+index*8`。其他平台分支在 `0x1093CB0` 與 `0x1093D1E` 把 `4` 當作列舉方法的容量參數。

獨立 helper root `0x1092E60` 重複此模式：`0x1092ECB` 對平台回傳人數與 `4` 比較，`0x1092ED0` 截至 `4`；其他分支在 `0x1092E78` 與 `0x1092F31` 將容量參數設為 `4`。這些是**本機平台大廳成員列舉的四人限制**，即使建立呼叫的某個參數為 `8` 也不能忽略。間接平台方法的精確函式名稱仍未確定，因此沒有推斷服務端規則。

## 不可用來命名建立容量的字串

`numLobbyMembers`、`numSessionMembers` 的 xref 在通用 typed JSON parser root `0x1053F60`；`/lobby` 的 xref 在 root `0x12CB190` 中組合路徑與序列化欄位，該 root 在 caller `0x13374B0` 被呼叫。這些路徑及欄位不能替 `+0xA0` 函式的第一參數命名。`MAXMEMBERS` 位於一串 UI 大寫 token 中，與建立呼叫無已證資料流。captured readonly 另有 `"player" : { "max" : %u, "capacity" : 4 }` 的 component 統計格式字串；其唯一直接 xref 為 `0x56E7EC`，同段的 `%u` 值讀自 `0x56E7DE [rdi+0xEA0894]`，位於大型診斷輸出 root `0x56A920`。`player_pool_probe.py` 在捕捉 code 範圍內只找到這一筆對 `0xEA0894` 的直接位移存取，**未找到分配器資料流**；字串中的 `capacity:4` 不足以證明任務中的 player pool 實際上限。下一個具體缺口是辨認 root `0x56A920` 的 `RDI` 診斷來源及真正分配／建立 player component 的 caller，不能從此格式字串反推。

## 可重播與精確缺口

於工作區根目錄，用尚不存在的輸出檔名執行：

```powershell
python five_player_feasibility_20260927/creation_path_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output NEW-creation-path-evidence.json
```

目前的首要缺口是 writable global RVA `0x3326340` 指向的設定實值、RVA `0x3326308` 對應的平台介面與其 `+0xA0` 及 `+0x30` 下的 `+0x18` 函式目標、兩函式的參數定義、RVA `0x3326E40` 與 `0x3326348` 的分支旗標實值、以及服務端建立回應。原捕捉沒有 writable globals 或 heap，且 `runtime_verified=false`；本輪沒有五人連線測試。
