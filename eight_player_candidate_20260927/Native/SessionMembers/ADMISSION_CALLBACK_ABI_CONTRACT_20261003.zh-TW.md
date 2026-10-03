# Admission callback ABI 契約（2026-10-03）

本契約鎖定 Steam build `25480438` 的 `game.dll` 證據。驗證器只讀取倉庫內已保存的反組譯與只讀擷取資料；不啟動遊戲、不存取程序、不呼叫 native 函式、不寫入記憶體、不安裝 hook，也不產生 patch。

## 已鎖定的邊界

- Host admission 的兩個間接呼叫：`0x108DDC7` 的介面表 `+0x08`，以及 `0x108DE09` 的介面表 `+0x50`。
- 兩者在保存的 call shape 中都使用 `RCX=[network_context+0xB390]` 與 `RDX=[r12]`；這兩個值仍然只是 opaque owner/id，沒有證據可把它們命名成 `PeerId` 或玩家索引。
- 呼叫之間有 `[r12+0x20] = 7` 的 32-bit state 寫入。這個數值的 enum 意義未解碼，不能當成玩家數量或索引。
- Host-to-client dispatcher 呼叫 `0xBE4910`，本機路徑再呼叫 `0xB90B20`；保存的 loop 是四次、`0x38` bytes stride。`[RDI]` 是 record `+0x20` 的 state；state <5 會跳過，而 state >=7 會產生 byte 旗標。它不是 network index 5～7 的 gate，這裡也沒有 state 的上限。
- Join handler 另有 `[object+0x50] -> [returned+0x28] -> call r8` 的 nested probe，以及 `0x13EFF30` 的 reject／cleanup 候選。它不能直接視為 host admission 的 `table+0x50` target。

## ABI 解讀規則

| 邊界 | 保存證據 | 目前可用 ABI | 未證明欄位 |
| --- | --- | --- | --- |
| `table+0x08` | 間接 call site | Windows x64 register shape；target 未解析 | return、state consumer、owner lifetime、cleanup |
| `table+0x50` | 間接 call site | Windows x64 register shape；target 未解析 | return、event/state meaning、cleanup |
| `0xBE4910` | host dispatcher + saved sender body | 六個位置參數（四個 register、兩個 stack）的 opaque 來源 | return contract、record ownership、receiver compatibility |
| `0xB90B20` | client insert call site + saved body | 六個位置參數的 opaque 來源與 direct target address | input 語義、return、capacity、remove/reset ABI |
| nested probe | join handler disassembly | `EAX-1` mask 接受 {1,2,5,6}；{1,5,6} 直接到 `0x108C043` | target、inputs、status enum |
| `0x13EFF30` | join handler direct call | `AL` 被後續測試 | inputs、return meaning、rollback ownership |

「target address 已知」只表示反組譯中存在 direct call；「target ABI 已證明」需要參數、回傳、owner lifetime、錯誤回滾與逆向 cleanup 的完整證據。目前所有 callback 的 `proven` 都維持 `false`。

## 八人改造的 fail-closed 要求

在 target、return、state、cleanup 四組 ABI 都閉合前，不能把 `4` 改成 `8`，也不能以 sidecar 取代未解析的 native callback。必須先證明：

1. admission success/reject 的回傳值與狀態轉換；
2. peer、roster ordinal、network index 的獨立映射；
3. 第五至第八筆 record 的 owner、serializer、receiver 與資源 handle；
4. 離隊、重連、房主轉移、reset/unload 的完整 inverse path。

收據 `admission_callback_abi_contract_20261003.json` 會拒絕任何來源雜湊、指令 bytes、build 或遊戲映像指紋漂移，並固定 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。
