# Receive callback-vector dispatch（固定 capture 25480438）

本輪從既有 code capture 追到一個先前因為沒有 unwind entry 而漏掉的 leaf dispatcher：`game.dll+0xBC2D10`。新增 `verify_receive_dispatch_entry_20261002.py` 與 JSON verifier，僅讀離線 capture，沒有存取遊戲程序、沒有呼叫函式、沒有 patch 或注入。

## 已閉合的 callback-vector ABI

`0xBC2D10` 的 17 bytes 為：

```asm
mov eax, r8d
mov rdx, r9
lea r8, [rip + 0x15895c3]     ; 0x214c2e0
jmp qword ptr [r8 + rax*8]
```

因此它的輸入／轉換是：

- `R8D` 是 callback selector/index；
- `R9` 是 descriptor/payload pointer，轉交給 `RDX`；
- `RCX` 保持不變；
- `R8` 改成 callback vector base；
- 以 `vector[selector]` 做尾跳。

固定表 `0x214C2E0` 的第 `168` 項（`0xA8`）精確指向 `0xBABA80`。`0xBABA80` 再解碼 descriptor 的 `+8/+0x18/+0x28/+0x38/+0x48` 並呼叫 `0xB90B20`。

## Constructor 與實際 consumer

`0x134D470` constructor 在 `0x134D5AC` 取 `0xBC2D10`，並在 owner `+0xB3F8` 寫入它。這是 callback vector 的初始化／註冊關係，不是 hash→selector 證明。

已找出多個把 owner `+0xB3C0` callback vector 傳給 service method 的 code site：

| vector base | service 間接呼叫 | slot |
|---|---:|---:|
| `0xB99F22` | `0xB99F39` | `+0x138` |
| `0xBBFAE2` | `0xBBFAF9` | `+0x138` |
| `0x1089602` | `0x108960D` | `+0x138` |
| `0x108FE13` | `0x108FE25` | `+0x138` |
| `0x134F511` | `0x134F528` | `+0x138` |
| `0x134F487` | `0x134F4A0` | `+0x140` |

這些 site 證明 callback vector 被交給外部 service/API；它們沒有在 capture 中提供 service-side hash registry，也沒有證明某一個 service event 會以 selector `168` 呼叫 `0xBABA80`。

## 仍未閉合的關係

- `0x4804FCF4` 只在保存 code capture 的 `0xBE4981` sender immediate 出現；沒有同一 capture 中的 hash→selector table。
- `0xBDE430` 是 generic send-side dispatcher，不能直接當 receive dispatcher。
- `0x134D470` 只是初始化 callback vector；不能把 constructor 的 writes 當成事件映射。
- 因此 verifier 明確輸出 `hash_to_selector_proven=false`、`production_hook_ready=false`。下一個必要資料是 service/network receiver side 的 hash/event registry，或一次只讀 runtime callback trace，證明 hash `0x4804FCF4` 進入 selector `168`。

Machine result: `receive_dispatch_entry_verification_20261002.json`。
