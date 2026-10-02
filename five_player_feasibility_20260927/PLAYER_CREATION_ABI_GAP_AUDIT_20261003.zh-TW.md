# Player creation ABI 缺口審計（固定 build 25480438）

本審計把已保存的 `0x1086460 → 0xFDC140 → 0x581320/0x581780 → 0x540920` 指令證據接成一條可重播的 ABI 圖。它只讀保存的 disassembly/evidence，不存取遊戲程序、不呼叫 native function、不寫入記憶體、不安裝或產生 patch。

## 已固定的 ABI

1. `0x1086460` 對 `owner+0x163ac` 的 network index 做 `cmp ...,4`，`jae 0x108624d`；index `4..7` 因此不會進入一般 player resource 建立路徑。
2. 接受分支在 `0x10868d7` 呼叫 `0xFDC140`，參數可由相鄰指令固定：
   - `RCX = rsi + 0xe49f0`：建立／resource context。
   - `RDX = eax`：前一個 resource loader 回傳的 handle。
   - `R8 = rdi`：player entity resource hash。
   - `R9 = rbp + 0x2b0`：本次建立的 stack metadata。
3. `0xFDC140` 將四個參數保存為 `owner=rsi`、`metadata=rbp`、`resource_hash=rdi`、`resource_handle=ebx`。它以 `owner+0xf32f14` 的 counter 形成 record，寫入 `record+0/+8/+0x10/+0x14`，再派發：
   - `0x581320(rcx=owner+0x40, rdx=record, r8=metadata, r9=owner+8)`。
   - `0x581780(rcx=owner+0x40, rdx=record, r8=metadata)`。
4. `0x581320` 依 entity component list 查 `owner+0x40 + index*8 + 0xf0c110/0xf0cb30`，並把 entity record/metadata 傳入 callback；它同時更新 `owner+8` 的 ordinal map、兩組 flags、count，失敗時把 `record+0x10` 留為 `0x7fff`。
5. `0x540920` 是第一階段 roster leaf，仍有 `cmp eax,4`；成功時增加 global roster count/active count，並寫入 `roster+0xe8 + ordinal*8` 的 inline pointer table。

## 對 4..7 sidecar 還缺的證據

目前沒有安全證據可把 `cmp 4` 改成 `cmp 8` 後直接發布：

- 沒有證明 `0xFDC140` 的 resource record、`owner+8` map/flags/count、callback table 與 roster pointer 能在 index `4..7` 以相同 generation 成功回滾。
- `PLAYER_RESOURCE_REVERSE_CLEANUP_AUDIT_20261003` 已補上 player-resource record、handle、component callback、owner+8 reverse map 與 roster remove 的固定釋放鏈；仍沒有每個 partial callback failure 的 idempotent unwind、重入安全或 owner quiescence 證據。
- 已有的 component 238 cleanup 證據仍只證明 owner 的 `+0xe9fc98` 可經 `0x873a70/0xb2fc70` 移除；新的 reverse cleanup 報告也沒有把 index 4..7 runtime 建立或部分失敗回滾推廣成已完成。
- `0x800` 是 resource record 搜尋與環繞上限，不是玩家容量，不能拿來代替 8 槽契約。

因此 sidecar 必須分開保存 network index、roster ordinal、resource record ordinal 與 component-map ordinal，並在 resource record、兩段 callback、roster 插入四個邊界各自記錄 generation 與 rollback owner。完成 owner migration、reconnect、thread quiescence 後，才有條件製作 native hook；本審計不產生 production patch。

## 重播

```powershell
& 'C:\Program Files\Python312\python.exe' five_player_feasibility_20260927/player_creation_abi_gap_audit_20261003.py `
  --output five_player_feasibility_20260927/player_creation_abi_gap_audit_20261003.json
& 'C:\Program Files\Python312\python.exe' -m pytest -q five_player_feasibility_20260927/test_player_creation_abi_gap_audit_20261003.py
```

結果中的 `installable=false`、`index_4_to_7_player_creation_proven=false` 與 `multiplayer_verified=false` 是刻意的 fail-closed 狀態。
