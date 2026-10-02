# Confirmed-peer 5–8 admission 邊界（2026-10-02）

這份 ABI inventory 使用 PID `38588` 的固定 build 25480438 只讀擷取。擷取讀取四個固定 `game.dll` 區段，沒有呼叫、寫入、注入或 hook；`multiplayer_verified=false`。

## Host confirmed-peer sender

`game.dll+0x108C760..0x108CD7C` 是完整可解碼的 host sender body：1564 bytes、SHA-256 `633d40a8f3815a1451064a62260f6657524ff5159d5b0c48e803ee883a150f4d`。Windows x64 入口參數是 `RCX=host/session state`、`RDX=peer handle`、`R8=join/transport context`、`R9=auxiliary value`。函式保存 `RBX/RBP/R13/R14`，建立 `0x188` stack frame 並驗證 security cookie。

確認的四槽邊界：

| RVA | 作用 | 八槽要求 |
| --- | --- | --- |
| `0x108C7EB` | 搜尋 `session+0x20`，每筆 `0x38` bytes，最多 4 筆 | 連同配置、離隊、重連、migration 和 cleanup 一起改成 8 |
| `0x108C81A` | `entry+0x20 - 1 <= 3`，只接受 ordinal 1–4 | ordinal/resource map 必須證明支援 1–8 才能改為 7 |
| `0x108C8E7` | 從 `session+0x40`、stride `0x38` 發送 4 筆 | 發送表、接收表和所有生命週期路徑必須同時擴展 |
| `0x108C9BC` | 對 `root+0x16418`、stride `0x10` 做 4 次 side-event loop | event table、序列化和 receiver 必須同時擴展 |

`0x108C878` 寫入狀態值 4，`0x108CA2D`、`0x108CA3B`、`0x108CBAD` 是暫時 event record 欄位；它們不是玩家容量，不能盲改成 8。

## 外部 admission/receiver 邊界

- `host_capacity_gate` `0x108C18F` 以 `4 - occupied` 計算空位，並把 `r8d=4` 傳給 transport callback。
- `host_index_allocator` `0x108C3D8` 內有 `ecx < 4` 的空槽搜尋，以及 `r14d < 4` 的 stride `0x40` 記錄表迴圈。
- `client_confirmed_peer_insert` `0xB90B20` 是接收端建立記錄的另一條生命週期，不能只改 host sender。
- sender 會呼叫 transport/event serializer（`0xBE5490`、`0xBE3CF0`、`0xBDE430`、`0xBE4910` 等），它們的 payload capacity、receiver schema 和錯誤回滾尚未以可寫 heap/服務回覆證明支援 8。

## 結論

只把 sender 的 `cmp eax,4`、loop count 或 ordinal compare 改大，會越過現有 host/session 表或把第五筆送到四槽 receiver，不能形成安全 patch。`confirmed_peer_admission_live_abi_20261002.json` 和 `confirmed_peer_admission_sidecar_adapter.py` 已加入 fail-closed gate；sender-only 或缺少 owner-keyed sidecar、8-record storage、receiver/serializer、migration/cleanup、unwind proof 的方案一律拒絕。當前 `installable=false`，不代表已完成八人联机。

可重現驗證：

```text
python verify_confirmed_peer_admission_live_abi.py --artifact confirmed_peer_admission_live_abi_20261002.json
python -m unittest -v test_confirmed_peer_admission_sidecar_adapter.py
```
