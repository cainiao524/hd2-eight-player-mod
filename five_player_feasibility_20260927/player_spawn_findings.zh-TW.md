# Confirmed peer 後續與四候選 respawn 更新：固定版本離線證據

本頁只分析 Steam build `25480438` 的既有唯讀捕捉。`player_spawn_replay.py` 先驗證 `capture-report.json` SHA-256 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5` 和 `captured-data.bin` SHA-256 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`，再按 unwind fragment 檢查 pin 的指令邊界；逐條 bytes／SHA／root 與 state switch table 保存在 `player_spawn_evidence.json`。沒有執行或修改遊戲。捕捉的 `runtime_verified=false`。

## Confirmed peer append 的直接後續

`0x10872C0` 在 `0x10872D5` 把收到的 `R8` peer identifier 存入 `RBX`。其 append 在 `0x1087333–0x108737B` 以 `count << 5` 定位 client record，把從 `[rsp+0x78]` 讀出的 player-index dword 存入 `record+0x14`（`0x108736A`）。迴圈結束後，`0x108751C mov rcx,rbx`、`0x108751F call 0xB5EA90` 只把 **peer identifier** 當作該函式的第一參數；並沒有把 record pointer 或剛存下的 player-index dword 傳入。另一 receiver root `0xB90B20` 亦先把其 `RDX` peer identifier 存入 `RDI`（`0xB90B46`），append 時在 `0xB90C12` 寫 `record+0x14`，後續 `0xB90E6B–0xB90E6E` 僅以 `RDI` 呼叫 `0xB5EA90`。

`0xB5EA90` 遍歷一張 runtime registry：其中一個分支查詢 8 槽、0xC0 stride 的表，加入 peer identifier，並呼叫 `0x1382C50`；其內用欄位 descriptor 呼叫 `0xBDE430`。另一分支在 `0xB5ED35` 把 peer identifier 放入 `RDX`，`0xB5ED3F` 呼叫 `0x66FBF0`。後者保留此值於 `R12`（`0x66FC20`），並在 `0x6702DA–0x670405` 交給 `0xBEC910`；`0xBEC910` 於 `0xBECB84–0xBECB89` 用 descriptor 呼叫 `0xBDE430`。所以目前可重播的直接路徑是**新增 peer 後傳送／同步資料**，尚未找到由 `record+0x14` 進入 player entity allocator 的資料流。這不否定其他未解析的事件回調或引擎分支可能使用該欄位。

## 另一條實際 gameplay 更新只有四個候選序號

從全域更新 root `0xAB5000` 的 switch 看，`0xAB609B` 讀一個 game-state 整數、`0xAB60A2` 減一，位於 captured code `0xAB7664` 的六項 jump table 把 **state 4** 指向 `0xAB60EF`，接著 `0xAB60F9` 呼叫 root `0xACBE60`。此函式內有「Player ... WaitingForRespawnTimer」及「Player ... Spawned」停滯紀錄字串；其後分支呼叫 `0xAC7280` 與 `0xAC7BE0` 處理此狀態候選。這定位的是 state-4 player／respawn 更新路徑，並非已證的初次入房建角或唯一出生流程。

`0xACC28A` 從未捕捉的 writable global RVA `0x3326468` 讀取一個物件；`0xACC297` 讀其 `+0x84` 動態 count。函式先在 stack 建立**四項** score 與序號組合：`[rbp+0xAF0]`、`+0xAF8`、`+0xB00`、`+0xB08`。當不同的資料分支計算 score 時，序號分別寫為 `0`（`0xACC30C`）、`1`（`0xACC394`）、`2`（`0xACC424`）、`3`（`0xACC4B4`，`EBX=3` 來自 `0xACC122`）；缺少來源時的 fallback 也把相應序號留在高 32 bits。`0xACC541` 以常數 `4` 排序這四項，`0xACC605–0xACC617` 再把 loop counter 設為 `4`。

每次迴圈在 `0xACC620` 從該 stack 項取 **roster ordinal**，`0xACC622` 與動態 count 比較；合法時 `0xACC638` 從 `[r14+ordinal*8+0xE8]` 取 player 狀態物件。`0xACCA1D–0xACCA31` 將 stack 指標加 `8`、counter 減 `1`，恰好巡覽四項。因為四個 ordinal 是 `0..3`，若 `+0x84` count 真能大於 `4`，此段也沒有第 `5` 個 ordinal 的候選。**這是某個 state-4 gameplay／respawn 批次的四項處理上限，不是已證所有 player entity 的分配容量。**目前也沒有證據把這些 roster ordinal 等同 host 分配的 network player index；兩個結構的來源不同。

`0xACC8A5–0xACC8C0` 的狀態分支呼叫 `0xAC7BE0`。該函式在 `0xAC7C29–0xAC7C56` 先查另一個動態 peer-ID 清單，後續試算 spawn 位置、`0xAC81F2` 最多嘗試 16 個位置，並透過 `0xAC8343 call 0xBE1920` 送出含位置資料的 descriptor event；`0xBE19F9` 再呼叫 `0xBDE430`。`16` 是位置嘗試數，並非玩家容量。此 bounded 路徑中尚未找到 player entity 的配置器或實際建構指令。

## 精確缺口

要把兩條路徑閉合，須解析 runtime event hash 對 receiver 的登錄、追出 `record+0x14` 的真正讀者，以及 `0xAC7BE0` 位置事件的接收端／player entity 建立器。還需辨認 state-4 roster 物件 `+0x84` count、`+0xE8` pointer table 的來源與實際容量，並確認其他 game state 或 respawn 路徑是否處理第五位玩家。現有證據只證明這段硬編碼四候選處理會成為擴八人時需處理的獨立 gameplay 障礙。

重播（請用不存在的新輸出路徑）：

```powershell
python five_player_feasibility_20260927/player_spawn_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output NEW-player-spawn-evidence.json
```
