# 0x10937A0 成員狀態更新邊界（2026-10-02）

這份結果直接從已保存的 build 25480438 只讀擷取重建，沒有寫入或呼叫遊戲程序。

## 已恢復的實際 ABI

- RVA `0x10937A0..0x10945D8`，3640 bytes，SHA-256 `929b6b1a3163e7b405d92d90d44c19dd4b2dc3d592115d2bb3e0383a1e719a69`。
- 完整解碼 819 條 x64 指令；保存 `RBX/RBP/RSI/RDI/R12-R15`、`XMM6`，使用 `sub rsp, 0x308` 和 security cookie。
- 輸入是 `RCX = platform/member owner 子物件`；已知呼叫者沒有穩定使用回傳值。
- `0x108F078` 把根物件的 `+0x1C00` 傳入；`0x134E44A` 和 `0x13F788A` 把根物件的 `+0x1D470` 傳入。這三個子物件不能在 sidecar 中混用。
- 第四個相鄰呼叫 `0x10944FC` 在同一 routine 內使用 `RCX = owner` 呼叫 `0x1093590`，其結果會影響狀態分支。

## 為什麼不能只改 4 為 8

完整證據列出 71 個 owner 欄位存取和 14 個立即數 `4` site。除了 `owner+0x1B58+8*i` 成員 ID 緩衝區和 `owner+0x1BB0` 計數器，routine 還會讀寫 `+0x1B78`、`+0x1B7C`、`+0x1B80`、`+0x1B84`、`+0x1B98`、`+0x1B9C`、`+0x1BA0`、`+0x1BA4..+0x1BA9`、`+0x1BAC` 等控制欄位。`+0x1B78` 緊接在原本四個 8-byte ID 之後；把第五個 ID 寫入 inline buffer 會覆蓋狀態欄位。

routine 內還有多個間接 callback、狀態轉換、清理呼叫，以及依照 count 的迴圈（包括 `0x1093DA8..0x1093E26` 和 `0x1094381..0x1094452`）。因此單獨替換 consumer、改寫容量常數，或使用沒有 owner lifetime/exception ABI 的短 stub 都不能證明安全。

## Sidecar 結論

目前產物 `platform_member_state_update_disasm_20261002.json` 僅是 exact captured evidence，`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。在可以生成可安裝補丁前，必須先完成：

1. 以確切 `RCX` 子物件為鍵的 sidecar 所有權、建立、離隊和清理；
2. 對所有 inline ID/count reader/writer 做一致的 sidecar redirect，同時保留相鄰控制欄位；
3. 綁定所有間接 callback、`0x1091800`、`0x1093120`、`0x1093280` 清理路徑及其失敗回滾；
4. 驗證 x64 unwind、重入和 callback 中途失敗時的 owner 狀態；
5. 以五至八個獨立帳號執行真實同任務驗收。

## 可重現驗證

在本目錄執行：

```text
python -m unittest -v test_platform_member_state_update.py
python verify_platform_member_state_update.py --artifact platform_member_state_update_disasm_20261002.json
```

目前結果為 2/2 測試通過，並回報 `passed_exact_state_update_evidence`；這不代表多人聯機成功。
