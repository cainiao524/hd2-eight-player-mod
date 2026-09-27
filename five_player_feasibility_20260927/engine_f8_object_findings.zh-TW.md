# EXE `0x8CCFA0` 物件建立路徑：保存片段的一層 CFG

分析只讀已保存的 `engine_callee_live_20260927_1.json`，檔案 SHA-256 `157ddf9f9f9c04265dbc80109441af7090fcf78316e8642781857668348f129a`。其中 EXE RVA `0x8CCFA0` 的 4,096 位元組區間 SHA-256 為 `1037567f291f256b22eab4d927b2f4f6d454d9eb5e36b0753b64219705b010e2`，重讀相同。上層 `0x8C6730` 使用先前保存的 `interface_probe_live_20260927_1.json`，檔案 SHA-256 `a45e5f5b1647d808b8b7716fd750e4a894ab39a3021b52a0b10c404403a8b85f`。逐指令 bytes/SHA、分支邊及未追入的 call 載於 [`engine_f8_object_evidence_v2.json`](engine_f8_object_evidence_v2.json)；[`engine_f8_object_replay.py`](engine_f8_object_replay.py) 可重播。未再讀取遊戲程序。

## 可確認的控制流程

從已知入口 `0x8CCFA0` 出發，只沿本區間內的直接分支及 fallthrough，得到 **188 條可達指令**。直接條件分支為 `0x8CD101 → 0x8CD0B0`、`0x8CD1C1 → 0x8CD170`、`0x8CD22E → 0x8CD257`、`0x8CD232 → 0x8CD248`；每條分支的兩側都留在保存區內。唯一可達的 `ret` 在 `0x8CD28D`，其後 `0x8CD28E` 為 `int3` padding，`0x8CD290` 起看似下一個函式。故本次沒有在第一個 `ret` 停下並漏掉其他直接分支。這是根據位元組與可達性推得的函式邊界，**沒有 EXE unwind 記錄作獨立證明**；呼叫目標及例外邊均未追入，4 KB 不能泛稱完整函式擷取。

## 返回 wrapper 與內部物件

`0x8CCFBF` 保留傳入的 `RCX` 為 owner `R15`，`0x8CCFCE` 保留傳入的 `RDX` 為 `RBX`。函式透過 owner 的 `[owner]` 物件虛擬槽 `+0x30` 呼叫三次（`0x8CCFE0`、`0x8CD01A`、`0x8CD04F`），其 `R8D` 依次是 `0x28`、`0x150`、`0x3F8`，三次 `R9D` 均為 8；`RDX` 都指向堆疊上的暫存/輸出位置。第三次呼叫後的 `0x8CD059` 才將 `R9D` 設為 1，供 `0x5C2C40` 使用。前三次參數**看似大小與對齊參數**，但虛擬槽的實作未保存，不能將它命名為已證的 allocator 或服務 API。

第一次虛擬呼叫後 `0x8CCFF7` 取 `[RAX]` 為 `R14`，作為最終返回的外層 wrapper。第二次呼叫取得的 `[RAX]` 傳給 `0x8DC850`，原始 `RDX` 輸入此時作 `R9` 轉交（`0x8CD01D..0x8CD032`），其返回值存至 `[R14+0x10]` (`0x8CD03F`)。第三次呼叫後 `0x8CD064` 取 `[RAX]` 為 `RBX`，初始化這個較大的內部物件，最後在 `0x8CD214` 寫入 `[R14+0x18] = RBX`。`0x8CD265` 將 `R14` 移至 `RAX`，由 `0x8CD28D` 返回。

保存的上層呼叫點 `0x8C67AD` 呼叫 `0x8CCFA0`，於 `0x8C67B7` 取返回 wrapper 的 `[RAX+0x18]` 作下一次呼叫的 `RCX`，於 `0x8C67BB` 把入口第一個 32 位元整數寫至 wrapper `+0x20`，`0x8C67BE` 把另一 byte 寫至 `+0x24`；`0x8C67C2` 呼叫 `0x8E1370`，並以 `EDX` 再次傳同一個第一整數。外層 wrapper 的疑似 `0x28` 大小容得下 `+0x20` dword 及 `+0x24` byte。**這個整數的業務意義仍未確認**；本路徑不能單獨將它叫作 MaxPlayers、房間人數或玩家索引。

## owner 指標列與服務線索

`0x8CD221/225` 讀 owner `+0x10` 計數與 `+0x14` 容量；`0x8CD229/22C` 比較 `count+1` 與容量。若不足，`0x8CD232..0x8CD24E` 選至少 8 並視既有容量增長的目標，再呼叫 `0x8D0000`。`0x8CD261` 取 owner `+0x18` 指標列，`0x8CD279` 追加 `R14`，`0x8CD27D` 增計數。這是**動態 owner 物件列**；其中的 8 是增長門檻，不是已證的 lobby 成員上限。

本層還呼叫 `0x8DC850`、`0x5C2C40`、`0x12672E0`、`0x5C16E0` 和 `0x8D0000`，以及三次未解析的虛擬槽 `+0x30`。保存片段無法把任何一個具名確認為 Steam、PlayFab 或自有後端建立房間 API。`0x8CCFA0` 可確認為建立 wrapper/內部物件並加入 owner 列；上層隨後把整數交給 `0x8E1370`，該函式的語義需以其自身保存片段另行查明。沒有服務回應、房間建立結果或多人實測。

重播命令（使用新輸出路徑；程式拒絕覆寫）：

```powershell
python five_player_feasibility_20260927/engine_f8_object_replay.py --saved five_player_feasibility_20260927/engine_callee_live_20260927_1.json --prior five_player_feasibility_20260927/interface_probe_live_20260927_1.json --output five_player_feasibility_20260927/engine_f8_object_evidence.replay.json
```
