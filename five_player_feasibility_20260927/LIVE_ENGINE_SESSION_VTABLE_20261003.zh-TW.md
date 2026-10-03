# Engine session vtable 邊界捕獲（2026-10-03）

此檔案保存固定 build 的靜態唯讀觀測。它從已釘選的模組映像與候選全域位置讀取 bounded prefix，記錄 session 指標、underlying vtable 前綴、模組歸屬與反組譯；沒有呼叫 vtable、寫入記憶體、安裝 hook 或改變遊戲狀態。

## 解讀方式

- `GameSession` public C API table 是 plugin wrapper 層；underlying session vtable 是另一層物件資料。兩者不能直接互換。
- JSON 內的位址、RVA、短前綴和雜湊只對 `Build 25480438` 及記錄的映像雜湊有效。
- `candidate_global` 與 vtable 連結是靜態研究候選，並未被當作已確認的玩家、peer 或 Party 入口。

完整機器資料：[live_engine_session_vtable_20261003.json](live_engine_session_vtable_20261003.json)

## 結論

這份捕獲可用於下一輪 ABI 比對和 fail-closed 版本門檻，不能用來宣稱 session 支援八人、可呼叫 `add_peer`、或已完成 player creation。任何實際呼叫仍需獨立的參數、回呼、錯誤回滾和多人驗證證據。
