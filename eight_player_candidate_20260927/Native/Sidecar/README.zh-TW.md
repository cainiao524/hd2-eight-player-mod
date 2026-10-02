# 八槽 Native sidecar 生命週期原型

這個目錄是與遊戲程序隔離的 x64 sidecar 原型。它提供八個穩定的
network ordinal，並把 `peer_id`、resource handle、slot state 與 generation
綁在同一個 caller-owned table 中。

涵蓋的轉移：

- `reserve`：依序取得第一個空槽，狀態為 `PENDING`。
- `confirm`：只接受同一個 generation 的 pending token。
- `remove`：清除 identity 但保留 generation，保留 roster hole。
- `reconnect`：現存 identity 取回相同 token；離隊後重新保留同一個空槽並遞增 generation。
- `validate`：檢查容量、計數、狀態、generation、重複 peer/resource 與清理後的 stale handle。

所有 API 都是 fail-closed。八槽已用盡、generation 溢位、重複 peer 或
resource、stale token 及損壞的 context 都會回傳明確狀態碼。這份 DLL
沒有尋找、載入或寫入 `game.dll`、Party、PlayFab 或任何遊戲程序，也沒有
把 sidecar 自動接到 native call site。

## 建置與合成驗證

在目錄內執行 `build_x64.bat`，它會用目前的 x64 MSVC BuildTools 建立
`ep_sidecar.dll`，再執行 `ep_sidecar_test.exe`。測試涵蓋完整八槽、孔洞
保留、重連 generation、重複身份、stale token、generation exhaustion、
destroy 及 invariant validation。

`sidecar_report_20261002.json` 記錄建置、合成測試與 SHA-256。這些結果
只能證明 sidecar 自己的生命週期契約；仍不足以證明遊戲能接受第 5～8 個
peer，因此上層 native plan 維持 `executable=false`，也不能當作多人驗收。
