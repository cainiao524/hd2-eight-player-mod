# 1277920 roster mask reader 離線候選

本候選把固定 build 的 `1277920..1277F7B` 完整 body 搬到合成位址，保留原 map 查找、miss fallback、network mask 迴圈、`585B80` leaf、ring／資源流程與 direct calls。它只重定向兩個仍讀同一 roster 的 operand 到共用 B sidecar，沒有宣稱可安裝、可進程序或可完成多人任務。

## 固定來源

- body：`five_player_feasibility_20260927/roster_mask_reader_evidence.json`
- body range：`0x1277920..0x1277F7B`，1627 bytes、390 條指令
- body SHA-256：`aecf466c012f2e9ba64787a5108b1807753f55166b484d7a0c21c71a21e5d1ca`
- 固定 evidence SHA-256：`596a95bec61e765c4a5758c55b762c803e2a13b35d59f05788431d1cf0c55344`
- 固定 `585B80` leaf 與 jump table 只在隔離測試中使用；候選不改寫它們。

## B sidecar 重定向

map 仍以原 `S=global[0x3326468]` 查找 ordinal。兩個經證實的同 root 讀取改用 `R11` 的絕對基址，指令其餘欄位保持原編碼：

| 原位點 | 原 operand | B 目的 | 注入基址偏移 |
| --- | --- | --- | ---: |
| `0x12779F5` | `[RAX + R11 + 0x12C]` | `B + 0x64 + ordinal*0x70` | `-0xC8` |
| `0x1277A06` | `[RCX + R11 + 0x3B4]` | `B + 0x58C + ordinal*0x20` | `+0x1D8` |

第二列的加減由原位移直接計算：`0x12C - 0xC8 = 0x64`，`0x3B4 + 0x1D8 = 0x58C`。`1277A0E` 之後載入的 global `0x33269C0` 是另一張 mask 物件，保留原來源。

## 前置 guard 與 ordinary miss

guard 插在原 frame/cookie 建立之後、第一次讀取 `RDX+0xC` 的 `0x1277945` 之前，因此不會先寫 input `+0x10` 計時欄：

1. `global[0x3326468]` 不是候選綁定的原 roster 位址，設 `R10D=1`；
2. `RDX == 0`，設 `R10D=2`；
3. 其餘情況進入原 body。

guard 比較本身不改 caller 的 `RCX/RDX/XMM2`；拒絕路徑將 `RAX=0xFFFFFFFF`，保存 frame 內已使用的非 volatile 值，執行已捕獲的 cookie helper 後跳到外部 reject handler。helper／handler 的 volatile-register ABI、stack unwind 與生命週期都是明示外部契約。entity map ordinary miss 仍走原本的 `input+4/input+8` fallback，不會被當成 roster mismatch。

空 entity key、map 找不到 key、以及 map 回傳的 ordinal 不在 B sidecar 可讀範圍時，本候選不新增拒絕分支，仍採原 reader 的 map／fallback 行為；因此 B 的八格指標與 ordinal 範圍是外部初始化契約。只有 global binding mismatch 與 null input 在本候選中有明確 reject reason。

## 隔離驗證

```powershell
& 'C:\Program Files\Python312\python.exe' -B -m unittest eight_player_candidate_20260927.tests.test_native_roster_mask_reader -v
```

測試以 Unicorn 合成 RAM 執行 6 項檢查：完整 body relocation 與 SHA、兩個 B operand、兩種 guard reject、ordinary map miss fallback、到 `0x1277AA3` 的 bounded mask prefix，以及從 source 重新產生 bundle 的可重現性。結果為 6/6 通過；prefix 使用 network `0,3,4,7,31,32,FFFFFFFF` 與三組 mask，實際讀取次數符合原分支，變更 mask 不改變該 prefix 的 GPR/EFLAGS/XMM 狀態。

輸出與地址樣本：

- `verification/native_roster_mask_reader_addresses_synthetic.json`
- `verification/native_roster_mask_reader_bundle_synthetic.json`
- `verification/native_roster_mask_reader_verification.json`

## 明確限制

- 這是 fixed-build、offline bytes-only 候選；`installable=false`、`game_execution=false`、`multiplayer_verified=false`。
- 沒有存取遊戲程序、安裝 hook、配置 Windows unwind、啟動遊戲或宣稱五至八帳號成功。
- reject handler、`12FDE90`／ring／resource callback、indirect virtual call、同步與 reentrancy、B sidecar 的分配／初始化／發布／清理仍未完成。
- mask producer、session／peer admission、player index 來源與後續 UI／AI 容量不在此 reader 候選內。
- prefix 通過只證明保存的 synthetic path；不等於完整 function return 或 live network acceptance。
