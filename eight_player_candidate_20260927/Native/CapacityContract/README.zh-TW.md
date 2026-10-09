# CapacityContract Native ABI

這個元件是容量設定與 Native bridge 的共同邊界。它只處理：

- build／schema／容量欄位驗證；
- component capacity 的最小值計算；
- host authority；
- 任務中升容的 reservation／quiescence 條件；
- atomic apply 與 generation；
- fail-closed report。

它不解析 RVA、不取得遊戲程序、不呼叫 `GameSessionCApi`、不建立 peer 或 Player
Clone，也不寫入 `game.dll`。`ep_capacity_contract_test.exe` 的成功只代表 C ABI
在 caller-owned 合成資料上通過。

建置與重現：

```powershell
cmd /c build_x64.bat
```

輸出 `ep_capacity_contract_passed` 後，仍需由 Native resolver 提供真實的 Session、
Party、roster、entity、resource 與 network capacity，才能把 contract 接入 production
preflight。真實執行前，`native_runtime_verified` 與 `multiplayer_verified` 必須保持
`false`。
