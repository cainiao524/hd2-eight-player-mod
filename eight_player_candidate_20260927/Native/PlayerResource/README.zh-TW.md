# Native PlayerResource sidecar（離線候選）

此目錄把固定 build `25480438` 的三張 callback table 交易順序做成八格原生 C++ sidecar：`begin → first → second → third → publish → release`。每個 slot 都有 generation、owner epoch、peer/resource identity 和 callback lease；部分 callback 失敗會清除記錄，重複 release 返回 `EP_RS_ALREADY_RELEASED`，owner migration 必須先 quiesce。

它只驗證 player-resource 的所有權與回滾契約，沒有解析遊戲 RVA、呼叫 game.dll、安裝 hook、注入程序或提供 player creation ABI。component `239` 只是測試輸入，對應固定 audit 的第一張 callback table roster leaf；真正 callback 仍需由已解析的遊戲 ABI 提供。

建置：

```powershell
cmd /c build_x64.bat
```

輸出 `ep_player_resource_synthetic_passed` 只代表離線 C++ 契約成立，`production_executable`、`runtime_verified`、`installable` 與 `multiplayer_verified` 保持 `false`。

## Bridge transaction adapter（2026-10-03）

`ep_resource_bridge_adapter.h/.cpp` 把三階段 resource transaction 接到既有
`EP_NATIVE_BRIDGE` callback 形狀。`ep_resource_bridge_configure()` 產生的
Bridge config 會把同一個 caller-provided network index 傳給 confirmed-peer、
player-create、三個 resource stage 及 remove/reconnect；stage callback table
有明示的 version/size，metadata callback 也必須提供非零 resource hash、record
ordinal 與 component ordinal。

admit 的離線順序是 `resource begin → native confirm → native create → first →
second → third → publish`。任一 callback 失敗都讓 Bridge 走既有 remove compensation；
離隊先完成 native remove，再釋放 resource record，generation 和 network index
仍由 Bridge/Sidecar 契約管理。缺少 callback、版本不符、重複 identity、stage
順序錯誤和 resource metadata 不完整都會 fail-closed。

`ep_resource_bridge_adapter_test.exe` 覆蓋八筆 admission、三階段 publish、index 4
離隊／重連 generation、index 3 的第二階段失敗回滾與完整清理。這是離線 ABI-shaped
adapter；它沒有解析 RVA、呼叫 game.dll、安裝 hook 或證明第五至第八位真人聯機。

stage callback 若拋出 C++ exception，adapter 會把它轉成 failed stage，先消耗並釋放
callback lease，再交回 Bridge 的 remove/retry compensation。這避免 exception 把
resource record 留在 `inflight` 狀態而阻塞後續 cleanup；測試已覆蓋第三階段拋出例外。

## Live storage lifetime guard（2026-10-04）

`ep_resource_init()` 現在會拒絕對仍帶有 `EP_RESOURCE_MAGIC` 的 live table
重新初始化，返回 `EP_RS_BUSY`，避免把 active record、generation token 和
owner lease 靜默清零。呼叫方必須先完成 `ep_resource_destroy()`，再重用同一塊
儲存空間；新 table 的儲存空間必須先由呼叫方清零，這個保護與 Bridge adapter
的 live initialization guard 一致。

合成測試會在 index 4 仍為 `PENDING` 時嘗試重新初始化，確認呼叫被拒絕且原本的
state、generation、peer 和 resource handle 保持不變。這只修正 sidecar 的生命週期
錯誤，沒有把它連接到遊戲的 native callback ABI。
