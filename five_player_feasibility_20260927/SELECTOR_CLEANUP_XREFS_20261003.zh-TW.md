# Selector cleanup xrefs（2026-10-03）

這是固定 build `25480438` 的離線 code capture 重播；沒有開啟遊戲、沒有讀取 live process、沒有寫入、沒有 hook、沒有安裝。

## 結果

- capture SHA-256：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。
- 動態 registration wrapper `0x1094680` 的 direct `E8` caller：`0`（0）；其進入方式仍是 indirect/runtime registration。
- unregistration wrapper `0x1094710` 的 direct caller：`3`。
- status helper `0x1094780` 的 direct caller：`3`。

## Cleanup 呼叫點

| helper | call RVA | caller fragment | owner field evidence |
| --- | --- | --- | --- |
| `unregistration` | `0x133d477` | `0x133d460, 0x133d485, 0x2508910` | `global+0x1f028` |
| `unregistration` | `0x145f2ec` | `0x145f0f0, 0x145f466, 0x251ccb0` | `global+0x1f028` |
| `unregistration` | `0x145f732` | `0x145f640, 0x145f788, 0x251cce8` | `global+0x1f028` |
| `status` | `0x133c88a` | `0x133c702, 0x133c897, 0x2508894` | `unresolved` |
| `status` | `0x145f6b4` | `0x145f640, 0x145f788, 0x251cce8` | `global+0x1f028` |
| `status` | `0x145f74d` | `0x145f640, 0x145f788, 0x251cce8` | `global+0x1f028` |

三個 unregistration caller 的 fragment 都準備同一個 `global+0x1f028` 欄位作為 owner/context；其中兩個 call 前可直接看到 `mov global` 加 `0x1f028`，第三個以 `rbx` 傳入，且同一 fragment 先完成該加法。這可作為 owner-keyed cleanup sidecar 的靜態 binding 線索。

交叉核對公開 Better Lobby Management 同版資料後，`global+0x1f028` 被標為 lobby browser/network context handle，`0x1094710`／`0x1094780` 對應 browser start/busy 類操作。因此這組 cleanup ABI 應先視為 lobby browser owner，不能當成 confirmed-peer/player admission registry；selector→receiver 與八格 player lifecycle 仍需另外取得 runtime 證據。

## 限制

- registration wrapper 沒有 direct E8 caller，不能從 code capture 還原 runtime dispatch table、service heap 或實際 hash/selector。
- owner 欄位不是容量證明，也沒有證明 callback ABI、thread quiescence、migration、resource cleanup 或 player creation。
- `installable=false`、`runtime_verified=false`、`multiplayer_verified=false` 保持不變；任何 production hook 仍需獲得允許的 runtime callback/registry 觀測後再做。

可重播：

```powershell
& 'C:\Program Files\Python312\python.exe' -B five_player_feasibility_20260927/audit_selector_cleanup_xrefs_20261003.py `
  --write `
  --output five_player_feasibility_20260927/selector_cleanup_xrefs_20261003.json
```
