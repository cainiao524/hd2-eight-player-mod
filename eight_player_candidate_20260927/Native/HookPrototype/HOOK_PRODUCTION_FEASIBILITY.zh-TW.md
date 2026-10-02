# Host join hook 生產可行性報告（build 25480438）

## 已有證據

2026-10-02 的授權唯讀擷取保存了 `game.dll` 的 loaded-image bytes。第一個可採用普通函式入口 hook 的候選是：

```text
module: game
RVA:    0x108BC70
bytes:  40 55 53 56 41 54 48 8D 6C 24 E9 48 81 EC C8 00 00 00
length: 18 bytes
```

這 18 bytes 是完整指令：`push rbp`、`push rbx`、`push rsi`、`push r12`、`lea rbp,[rsp-0x17]` 和 `sub rsp,0xC8`。它在 capture 中位於函式開頭，沒有 branch 或 RIP-relative operand，因此可以由 scaffold 的 trampoline 原樣複製後跳回 `RVA + 18`。前提是 production preflight 先再次驗證 build、模組和 site bytes。

目前 scaffold 已在 synthetic target 驗證：保存原 bytes、14-byte absolute jump、trampoline call-through、`RtlAddFunctionTable`、`FlushInstructionCache`、restore、`RtlDeleteFunctionTable` 和釋放 trampoline。

## 不適合標準入口 detour 的 root

`game.dll + 0x108C18F` 不是函式開頭，而是同一 admission 函式中段：

```text
mov eax,r14d
cmp [r9+0x58],rax
setne al
inc eax
...
mov ecx,4
sub ecx,eax
cmp ecx,r13d
```

這裡依賴前面建立的 `r12/r13/r14/rbp`、stack locals 和 branch continuation。以普通 C/C++ detour 覆蓋會遺失呼叫現場或分支語意，不能只替換成 `8`，也不能使用與函式入口相同的 API。它需要經審核的中段 code cave、完整寄存器保存、兩個 continuation，以及 sidecar capacity result 的明確 ABI。

## Scaffold 的安全界線

`ep_install_hook` 只接受呼叫者提供的 target、detour 和已核實的指令邊界，並限制 14 至 64 bytes。它沒有自動找 RVA、沒有掃描程序、沒有 `game.dll` patch export，也沒有 PlayFab、Party 或 player resource callback。`ep_verify_host_join_site` 只讀取並比較 host join prologue；它不寫入程序。

因此報告中的 `executable=false` 是正確狀態。synthetic DLL 通過不等於 production hook 已通過。

## 仍需的實機證據

1. 以固定 build preflight 再驗證 `game.dll` loaded-image 的 4 KiB site hash 和 `game.dll + 0x108BC70` 的 18-byte prologue。
2. 在不改變 admission 結果的觀察 hook 中記錄四人基線的參數、回傳值、失敗分支和 owner pointer，確認 sidecar owner 的真實生命週期。
3. 只接入 host join sidecar 的第 5 人試驗，確認 host confirmed-peer sender、client confirmed-peer insert 和 player creation gate 的事件順序。
4. 對 host migration、離隊、重連和 unload 執行 thread quiescence/rollback 試驗，確認沒有 stale callback 或舊 generation resource handle。
5. 在第五人通過後，依序做六至八人完整任務，並由八個獨立帳號記錄 peer、roster、entity、死亡、增援、撤離和結算一致性。

