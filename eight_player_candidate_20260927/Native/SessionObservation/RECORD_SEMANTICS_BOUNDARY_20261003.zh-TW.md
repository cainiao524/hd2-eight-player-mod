# Underlying session record semantic boundary（2026-10-03）

這份候選把保存的 `helldivers2.exe` disassembly 能證明的 record 關係固定成 fail-closed、no-call verifier。它不把 opaque bytes 命名成 PeerId、玩家、network index 或 Party member。

## 已證明的關係

- session `+0x138` 是被 count getter 直接讀取的 `uint32`，而 `+0x140` 是 record table。
- record lookup 對輸入 `i` 使用 `i * 0x30`，直接返回 table entry；該方法本身沒有邊界檢查，呼叫端必須先驗證 `0 <= i < count`。
- record 起始 qword 會被 identity predicate 與 `session +0x20` 比對；因此 verifier 只稱它為 `identity_token`。
- `session +0x130` 會由 owner accessor 原樣返回；其語義仍是 opaque。
- 已觀察到 record `+0x29` 被 accessor 在 identity 命中後讀取；只保留為 `observed_byte_29`。

## Fail-closed 規則

`ep_session_record_semantics.h` 要求 snapshot 已通過固定版本及雙讀穩定性門檻，重新讀取 `session +0x20`、每筆 record 的 qword 與 `+0x29`，拒絕超過八筆、重複 identity token、讀取失敗，以及無法唯一找出 self record 的資料。這些規則只建立 opaque record 與 session self key 的關係，沒有呼叫 vtable 或寫入遊戲記憶體。

```powershell
cmd /c build_record_semantics_x64.bat
```

合成測試只驗證靜態邊界，不代表欄位是 PeerId／network index，也不代表第五至第八名玩家可加入。

