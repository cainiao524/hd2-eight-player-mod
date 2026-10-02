# 固定 build 25480438：平台介面 live probe 補充

這份補充只使用使用者授權的唯讀程序 probe `interface_probe_live_20261002.json`。它沒有呼叫遊戲函式、沒有寫入記憶體、沒有 hook／注入，也沒有進行多人測試。

## 目前取得的介面目標

在 PID 42592、build 25480438 中，固定 global 讀值為：

| 路徑 | 執行期值 |
|---|---|
| `game.dll+0x3326308` → API root | `0x7ff669508d80` |
| API root `+0x30` → table | `0x7ff66950ba30` |
| table `+0x18` | `helldivers2.exe+0x3494b0` |
| API root `+0xf8` → table | `0x7ff66950de70` |
| table `+0xa0` | `helldivers2.exe+0x8c6730` |
| `game.dll+0x3326340` → config root | `0x1e9ab9f0080` |
| config root `+0x20` | `0` |

欄位二次讀取保持一致，程序映像和六份固定版本指紋均相符。

## `+0xa0` 目標的可見 ABI 形狀

live prefix 顯示 `helldivers2.exe+0x8c6730`：

- `ECX` 先保存到 `ESI`；`DL` 零擴展到 `EDI`；`R8` 被當成輸入記錄指標。
- 建立物件後，把 `ESI` 寫到新物件 `+0x20`，把 `DIL` 寫到 `+0x24`。
- 讀取輸入記錄 `R8+0x10/+0x18/+0x20/+0x28/+0x30/+0x38`，再呼叫兩個內部 helper。
- 這與既有靜態建立路徑的 `+0xa0` 間接呼叫形狀一致；在 config `+0x20 == 0` 的路徑，caller 會傳入 `owner+0x1b90 + 4`，靜態證據顯示其第一個整數參數為 `8`。

這是「平台物件建立資料流可能已有八的欄位」的正面證據，但仍不能命名為 PlayFab／Party max member，也不能證明後端接受八個帳號。`+0xa0` 的函式名稱、完整參數、返回物件生命週期和服務端回應仍未閉合。

## 另一個 API 目標

`API root+0x30` 的 `+0x18` 目前指向 `helldivers2.exe+0x3494b0`。可見前綴設定 `R9D=8`、`R8D=0x5e0`，再經由另一個 vtable 間接呼叫；這些值的語義尚未解析，不把它們當作玩家容量。

## 對八人實作的影響

目前最有價值的下一個固定版本工作面，是在不改寫平台 DLL 的前提下，追蹤建立物件返回 handle 進入 host owner、成員列舉與 confirmed-peer 發送的資料流。仍須同時補齊：

1. `0x1093C91`、`0x1092ECB` 等本機四人列舉與截斷路徑；
2. host four-slot records、allocator、pending、client append 與 player creation 的原生改接；
3. 真實第五帳號的 session response、角色建立、戰鬥、離隊／重連、撤離與結算。

在上述 ABI、owner lifetime 和多人結果未閉合前，Native Bridge 及 Package gate 必須維持 `executable=false`、`multiplayer_verified=false`。
