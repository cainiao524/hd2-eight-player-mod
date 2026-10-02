# Player resource reverse cleanup ABI 審計（固定 build 25480438）

本輪補上先前缺少的原生釋放鏈證據，完全重播既有 `capture-report.json`/`captured-data.bin`。沒有存取遊戲程序、呼叫函式、寫記憶體、注入或安裝。

## 已閉合的釋放鏈

`0xFDC780(context, flag)` 先釋放 context 的 resource owner，再循 `context+0xF3EF20` pending record pointer array，逐筆呼叫 `0xFDC820(context, record, flag)`，最後將 `context+0xF3EF18` 設為零。

`0xFDC820` 對每筆 record 已固定以下流程：

1. 讀 `record+8` resource handle。
2. 讀 `record+0x10` component/resource ordinal；`0x7FFF` 是尚未分配 sentinel。
3. 依 component list 呼叫兩張 cleanup callback table（`+0xF0DFB0`、`+0xF0E9D0`）。
4. 對 handle registry 呼叫 `0x172F8A0`，並對 `record+0x10` 相關 map 再執行刪除。
5. 以 `RCX=[context+8]`、`EDX=record+0x10` 呼叫 `0xFDDC80`，清理 owner+8 的反向 ordinal map。
6. 將 `record+0xC=0`、`record+0x10=0x7FFF`，呼叫 `0xB225F0(record)`，把 `record+8` 恢復成全域 sentinel 並清 `record+0x14`。

`0xFDDC80(owner8, key)` 的資料流也已閉合：

- `owner8+0xB020` 是 map table，count 在 `+0xB028`，每 entry 為 0x10 bytes。
- `EDX` 是要刪除的 key；找到後把最後 ordinal 的 `+0x1C`、`+0x201C`、`+0x281C` 複製到被刪位置。
- `owner8+0x18` 只在成功找到 key 後減一。
- count 為零或 key 缺失會返回，不會錯誤減少 owner8 count。

## 八槽 sidecar 的實際要求

這證明了 reverse map 與 cleanup 不是單一 `free(record)`：resource handle、component ordinal、owner+8 map/flags/count、callback table 與 roster pointer 必須以同一 generation 綁定。任何 callback 在中途失敗，都要撤回已完成的 callback、handle map、owner+8 map/flags/count 與 roster 寫入，再發布建立成功；目前 capture 沒有證明這種 partial failure rollback 或 re-entry idempotence，因此 verifier 保持 `installable=false`。

可重播 verifier：

```powershell
& 'C:\Program Files\Python312\python.exe' five_player_feasibility_20260927/player_resource_reverse_cleanup_audit_20261003.py `
  --evidence evidence/existing-code-evidence-25480438 `
  --output five_player_feasibility_20260927/player_resource_reverse_cleanup_audit_20261003.json
& 'C:\Program Files\Python312\python.exe' -m pytest -q five_player_feasibility_20260927/test_player_resource_reverse_cleanup_audit_20261003.py
```
