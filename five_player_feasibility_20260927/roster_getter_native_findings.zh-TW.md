# 606AD0 ID→network index getter 的完整固定證據

## 來源與可重跑範圍

本輪只讀 Steam build `25480438` 已保存 capture 的單一完整 unwind root `[606AD0,606B75)`；沒有掃描全 capture、接觸遊戲程序或安裝 hook。capture report SHA-256 是 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`，captured data 是 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`，capture identity 是 `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。

完整 body 為 **165 bytes／43 指令**，unwind `2424C2C`，bytes SHA-256 `96ce6884140adb9ae93688e042a2b5db7ffc1e59ffb45eb03188e6bab79abcfb`。[evidence](roster_getter_native_evidence.json) 的 `bodies['0x606ad0']` 固定 `bytes_hex`、每條指令 RVA／bytes／SHA／encoding、完整 CFG、兩個外部 RIP relocation、map 與 property sites、全部返回路徑。43 條指令由入口在靜態 CFG 中可達；所有分支均指向同 body 的指令邊界，沒有 call 或外部 branch，只有 `606B59` 一條 RET。[replay](roster_getter_native_replay.py) 對上述來源、body、unwind、每條 critical bytes、relocation、property offset／stride 與返回點施加斷言。

在 PowerShell、此工作目錄執行下列指令，指定尚不存在的輸出路徑即可重跑：

```powershell
$cap = 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438'
$env:PYTHONPATH = 'eight_player_candidate_20260927/.native-test-deps'
py -3.12 -B five_player_feasibility_20260927/roster_getter_native_replay.py --evidence $cap --output NEW-roster-getter-native.json
```

[evidence](roster_getter_native_evidence.json) 和 [recheck](roster_getter_native_recheck.json) 在同一固定來源上逐 byte 相同，SHA-256 均為 `1360863bfe1f1f6ce640ef049776d3b31703a1cbfe2bea3f90bf20555f69e0fd`；replay SHA-256 為 `ef2b9c3be43f04854cc4bdb1e8868b60d30dd4074d87124bf19953491be07c0c`。

## 實際 ABI、查表與返回

入口 EDX 是 **entity ID**；RCX 在此 body 沒有用來選 roster。`606AEA` 從 RIP global `3326468` 取得 S，`606AE4` 以 RIP global `3483C20` 比對 invalid ID。其後按 `S+D0` map pointer、`S+D8` capacity、`S+DC` empty-key sentinel、`S+E0` hash multiplier inline 探測。map bucket 是 8 bytes：`606B29` 讀 key，`606B5E` 讀 bucket `+4` 的 roster **ordinal**。此函式不寫 map、count、四陣列或 entity。

| 條件 | 原控制流 | 回傳 EAX |
| --- | --- | --- |
| 輸入 ID 等於 global invalid ID | `606AF1` → `606B40` | `FFFFFFFFh` |
| map capacity 0 | `606B0D` → `606B40` | `FFFFFFFFh` |
| 遇 empty key 且它不等於輸入 ID | `606B33` → `606B5A/5C` → `606B40` | `FFFFFFFFh` |
| 探滿 capacity 仍無相符 key | `606B3E` 落入 `606B40` | `FFFFFFFFh` |
| key 命中，但 map ordinal 為 `FFFFFFFFh` | `606B65` → `606B40` | `FFFFFFFFh` |
| key 命中，map ordinal 為其他值 `r` | `606B67` 將 r 乘 `20h`，`606B6B` 讀 property | property 的 network-index DWORD 原值 |

若輸入 ID 恰等於 map empty-key sentinel，原碼在 `606B5A` 再比對一次並可能按該 bucket value 走命中路徑；不能把「遇 empty bucket」不加條件地稱為 miss。所有路徑在 `606B45` 起還原 RBX／RBP／RSI／RDI，於 `606B59` 返回。沒有 `sub rsp` 或外部 call；原 prologue 使用入口 shadow/home space 保存這四個非揮發暫存器。若 property 內的 network-index DWORD 本身也是 `FFFFFFFFh`，回傳值與 miss 相同，但來源不同；此 body 不另行檢查 network-index 值。

## 唯一需要重導向的四陣列讀取

`606B67` 是 `48c1e005 shl rax,5`；`606B6B` 是 `428b8410b4030000 mov eax,dword ptr [rax+r10+3B4h]`。因此查得的 map ordinal `r` 只用來定位 **S+3A8h+r*20h+0Ch** 的 property network index，並把那個 32-bit 值原樣回傳。r 與 network index 是兩個不同量；函式沒有 `r<4` 或 `r<8` 的檢查，僅排除 `FFFFFFFFh`。若 r 是其他錯誤大值，原碼會進入錯位 property 讀取。

八格 sidecar 佈局的對應地址為 **B+580h+r*20h+0Ch**。候選若改接此 getter，需要在首次 property 讀取前驗 S binding、map backing／可探測 key、`r<8`、sidecar property 有效性及同一 roster 生命週期；保留原有 `FFFFFFFFh` miss 回傳與 property network word。這個局部 getter 證據不代表其它 network-index consumer、hook、unwind、多人執行已完成。
