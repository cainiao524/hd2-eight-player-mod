# 固定版本 live admission sites（2026-10-02）

`native_admission_sites_live_20261002_r2.json` 保存 PID `38588` 的只讀重讀結果。程序和 `game.dll` 都通過 build `25480438` 的既有 SHA-256 與 code pins；每個 site 讀取兩次相同，沒有呼叫、寫入、載入 DLL、hook 或注入。

## 已觀察的四人 gate

| RVA | live bytes / 結構 | 對八人改接的含義 |
|---|---|---|
| `0x108C18F` | `0x108C1B5` 的 `mov ecx,4` 計算 remaining capacity；`0x108C1C1` 的呼叫把 `r8d=4` 傳入；另一條錯誤/替代路徑傳 `r8d=9` | 不是單一比較常數；需要保存剩餘容量、caller locals、分支 continuation 和 helper ABI |
| `0x108C3D8` | `host+0x100` flags 迴圈在 `0x108C3E2` 比較 `ecx,4`；另一個 peer table 查找已是 `cmp eax,8` | host index allocator 同時含四槽 inline flags 和已有八項查找，必須分離兩種 ordinal/storage |
| `0x108C760` | host confirmed-peer table 從 `+0x20` 開始、stride `0x38`，`cmp eax,4`；`slot+0x14` 是 network index；另有 `cmp eax,3` 的 index branch | 第五至第八個 peer 不能直接延長 inline table，需 sidecar sender、local peer branch、event wrapper 和 cleanup |
| `0xB90B20` | client append 使用 `+0xC8` count、`+0xD0` record、stride `0x20`；部分查找迴圈已比較 `ecx,8` | client receiver 有可重用的八項查找形狀，但 record 後方 `+0x150` 是已用欄位，仍需搬移 append/remove/reset storage |
| `0x1086460` | 函式首條指令 `cmp [rdx+r8+0x163AC],4; jae ...` | player creation gate 明確拒絕 index `4..7`；只改條件不足，還需 resource、roster、component 和 cleanup ABI |

## 結論

這份 live capture 把第五人最小改接面收斂到 host capacity、host index allocator、confirmed-peer sender、client append 和 player creation gate。它沒有证明服务端接受、第五人角色建立或八人任务可玩；当前唯一安全路线仍是恢复真实 sidecar/dispatcher/owner lifetime 后生成可回滚 hook，再按五至八人逐级实测。

机器证据仍保持 `read_only=true`、`calls_made=false`、`writes_made=false`、`multiplayer_verified=false`。
