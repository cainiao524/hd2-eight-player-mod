# MenuScreenLoadout 建構／釋放／回呼 ABI 審計（2026-10-03）

這份審計重新解碼固定 build `25480438` 的離線擷取，將畫面物件的外層建構、每一個 widget 的建構、兩條釋放路徑、transition 回呼以及執行期四項護欄綁成同一份 machine-readable 契約。沒有讀取遊戲程序、呼叫函式、寫入、注入或產生 patch bytes。

## 已閉合的可重用函式對

畫面入口 wrapper `0x1465820` 先呼叫 `0x1467330` 釋放舊狀態，再跳到 `0x1466170` 重新建構。這條邊界表示重連／畫面重建不能只新增第 5～8 個 widget；釋放與重建必須使用同一份 owner layout。

| 生命周期 | RVA／目標 | 已確認行為 |
|---|---|---|
| 外層 screen constructor | `0x14A17E0` | 初始化 `+0x10` 的 `0x9F0` record，`mov edi,4`；在 `+0x53A78` 以 `0x1EE18` 步幅呼叫 `0x14AA5C0` 四次 |
| 單一 widget constructor | `0x14AA5C0` | 以 `+0x220` 呼叫內部建立，兩次呼叫 `0x14AA860` 初始化 nested state；自身還有 14、4、6 項內部初始化迴圈 |
| 外層 screen release | `0x1467330` | 以 `0x144DD70` 釋放相鄰 object，並從 `+0x57FC0` 每次 `+0x1EE18` 釋放四個 widget |
| 另一條 widget release | `0x1467720` | 從 `+0x55A20` 每次 `+0x1EE18`，有條件呼叫 `0x18A0FD0`，固定四次；尾端交給 `0x1397EE0` |
| widget transition | `0x1470A40` | 從 `+0x53A78` 每次 `+0x1EE18`，對每個 widget 呼叫 `0x189E080` 與 `0x1451100`，固定四次 |

這些基址不同是有意義的：建構／transition 從 widget 起點開始，兩條釋放路徑走 widget 內的不同 nested member。只將起點或單一 loop 的 `4` 改成 `8` 會遺漏 nested ownership。

## 尚未可安全搬移的讀者

`0x189D050` 在 slot helper 入口直接以 `cmp edx,4` 拒絕 index 4–7。`0x146E0A0` 的 runtime update 另有 record/ordinal guard，以及多個以 `cmp ...,4` 的候選 slot loop；這些路徑不在原先四槽 map 的簡單 constructor／release loop 中。因而完整八人需要同時處理 screen object、widget nested state、runtime guard、callback、清除及重連。

## 可實作的下一步

目前最小可實作步驟是新增**版本化 loadout sidecar 契約**：為八個 network index 保留 records、forward/inverse map、widget token、generation、pending／confirmed 和 release state；對應到 `0x14AA5C0` 的初始化、`0x189E080`／`0x1451100` 的 transition，以及 `0x144DD70`／`0x18A0FD0` 的釋放操作。sidecar 必須在任何 native callback、物件指標或資源 ABI 缺失時拒絕操作。

此步驟只建立可檢查的資料／生命週期契約；尚不能把它當成遊戲 patch。原生 loops、allocator、callback、UI package unload 及第五人實際畫面仍需在取得 writable object／完整 ABI 後逐一接線。

`loadout_lifecycle_abi_audit_20261003.json` 的固定檢查全部通過，但 `production_patch_ready=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false` 保持不變。

## 重播

```powershell
& 'C:\Program Files\Python312\python.exe' five_player_feasibility_20260927/audit_loadout_lifecycle_20261003.py `
  --evidence evidence/existing-code-evidence-25480438 `
  --output five_player_feasibility_20260927/loadout_lifecycle_abi_audit_20261003.json
& 'C:\Program Files\Python312\python.exe' -m pytest -q five_player_feasibility_20260927/test_loadout_lifecycle_20261003.py
```
