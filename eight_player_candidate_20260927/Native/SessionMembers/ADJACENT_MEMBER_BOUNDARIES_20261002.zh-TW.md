# 相鄰 platform member 邊界清單（2026-10-02）

固定 Steam build `25480438` 的靜態證據已整理到 `adjacent_member_boundaries_20261002.json`。來源 capture identity 為 `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。本文件只記錄可審查的指令邊界；沒有寫入遊戲程序、注入或聯機驗證。

## 已完成的 sidecar candidates

- `0x1093590`：14-byte exact entry detour，回滾恢復原 14 bytes，callback 位址仍是 template sentinel；Windows x64 unwind metadata 已附，靜態驗證通過。
- `0x10936e0`：leaf reader 的 14-byte exact entry detour，保存 `owner`、讀 sidecar `+0x44` 的 signed result，負值走 mode fallback；Windows x64 unwind metadata 已附，靜態驗證通過。

兩者都標為 `installable=false`，不能直接接到遊戲。

## `0x10937A0` 安全阻塞

`0x10937A0..0x10945D8` 是 3640 bytes 的 state update routine，不是可獨立替換的 leaf。已知路徑同時：

- 以 `owner+0x1BB0` 驅動 member loops，讀取 `owner+0x1B58+8*i`；
- 在多個位置寫入 member buffer、count，以及 `+0x1B78/+0x1B7C/+0x1B80/+0x1B84` 控制欄位；
- 仍有多個 `capacity=4` gate；
- 被 `0x108F078`、`0x134E44A`、`0x13F788A` 等 caller 使用。

因此目前不產生 `0x10937A0` 的 machine-code patch。14-byte entry detour 會繞過整個 state machine；mid-function detour 則需要每條分支的寄存器、owner lifetime、例外和 cleanup ABI，這些證據尚未完整。

## 清單範圍

JSON 內含來自現有 layout evidence 的 87 個 exact sites，按 RVA、root、欄位用途分類；它是 reader/writer 全清單（以目前 capture 的已知 pins 為範圍），不是對未知 native code 的完整保證。

靜態狀態：`runtime_verified=false`、`installable=false`、`multiplayer_verified=false`。已知 site 數：`87`。
