# Receiver callback-vector 入口（固定版 25480438）

本輪從固定 capture 找到先前漏掉的無 unwind leaf `game.dll+0xBC2D10`。它不是 hash registry，而是 callback-vector 的間接分派入口：

```text
mov eax, r8d
mov rdx, r9
lea r8, [rip + table]     ; table = 0x214C2E0
jmp qword ptr [r8 + rax*8]
```

因此已能精確描述入口 ABI：`R8D` 是 selector/index，`R9` 的 decoded descriptor 轉到 `RDX`，`RCX` 保持原 owner/context；selector 168 的表項指向 `0xBABA80`，再由它呼叫 `0xB90B20`。`0x134D5AC` 的 constructor bytes 也把同一個 leaf 寫入 owner 的 `+0xB3F8` vector。

另保存六個以 `owner+0xB3C0` 等位移取 vector、再經 service slot `+0x138/+0x140` 間接呼叫的 consumer。這些是可重播的 code/data wiring，並不證明哪個 service 把 `0x4804FCF4` 轉成 selector 168。

## 尚未閉合的邊界

`0x4804FCF4` 在固定 evidence 中只找到送端 literal；hash/event → selector 的 writable registry、service resolver、owner lifetime、cleanup/unwind 和第五至第八筆 player resource callback 仍未恢復。機器驗證 `receive_dispatch_entry_verification_20261003.json` 因此固定為 `hash_to_selector_proven=false`、`production_hook_ready=false`、`runtime_invoked=false`、`multiplayer_verified=false`。

這個結果把「接收 ABI 不明」收窄為「接收 vector ABI 已知、hash→selector producer 尚未知」，不能直接產生或安裝 patch。
