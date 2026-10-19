# Client confirmed-peer replication sidecar 契約（build 25480438）

這份 sidecar 是離線、caller-owned 的資料契約。它不尋找遊戲程序、不載入 `game.dll`、不注入、不改寫原生指令，也不聲稱已完成八人聯機。它只在收到已核對的 network index、peer identity、resource handle 和 callback 結果後管理一份可回滾的十六槽模型。

## 契約內容

- network index 只能是 `0..15`。Session／Party 分配出的 index 必須由呼叫者原值傳入 `ep_cr_append`；sidecar 不會把洞位壓成另一個 index。
- 五組已核對的 client fixed-four 陣列以獨立 ordinal view 表示：`adjacent_8`、`adjacent_16`、`adjacent_16b`、`confirmed_32` 和 peer-keyed search。每組都有自己的 count 和 `ordinal_to_index`。移除時只壓實該組 ordinal，其他組和穩定 network index 不變。
- `array_membership_mask` 必須明確包含 `confirmed_32`；peer-keyed `+0x150` 不會被推定與 confirmed-peer 一對一。
- append、confirm、remove、kicked、reset 都必須先經 callback。callback 使用完整五組 mask；callback 失敗會回滾，回滾 callback 也失敗時保留 `ROLLBACK` 槽位和 token，必須用 `ep_cr_retry_rollback` 收尾。
- generation 與 network index 綁定。離隊後的洞位可重用但 generation 增加，舊 token 永遠不能移除重連玩家。
- callback lease 以槽位保存。lease 未離開時拒絕 remove/kick/reset；migration 也必須等待所有 lease、pending 和 rollback 清空。
- host migration 是 begin／commit／abort 交易，owner key 與 epoch 只有 commit 才更新；epoch 必須遞增。
- owner callback 回傳失敗或拋出 C++ 例外時，入口回傳 `EP_CR_CALLBACK_REJECTED` 並釋放鎖。begin 失敗不建立交易；commit／abort 失敗保留原交易與 owner，讓呼叫者重試。callback 自己負責失敗時的外部副作用補償。
- 所有 mutex、callback 和 invariant 異常都 fail-closed。`ep_cr_production_enabled()` 固定回傳 `0`，所以這份 artifact 不能直接當作遊戲插件。

## 離線驗證

```powershell
cmd /c build_x64.bat
```

合成測試涵蓋十六個 stable index、index 16 拒絕、洞位與 ordinal compaction、generation fence、五組 mask、callback failure compensation、rollback retry、callback lease/quiescence、kicked/reset、host migration 交易和 production gate。owner callback 的 begin／commit／abort 各測試回傳失敗與拋出例外，確認失敗後鎖可再次取得、交易可重試、已確認玩家的 index／generation 保持不變。測試只載入本目錄剛編譯的隔離 DLL。

## 尚未證明的原生條件

目前資料沒有確認 client confirmed-peer native callback 的 register／return／cleanup ABI，也沒有證明 `player index` 語義、原生 entity 建立、資源生命週期、PlayFab／Party admission 或第五至第八帳號的 peer/entity replication。這些缺口關閉前，production、installable 和 multiplayer gates 都保持 false。

## Admission 與 client replication 連接（2026-10-13）

`ep_replication_bridge.h/.cpp` 把現有 `EP_NATIVE_BRIDGE` 與這份 replication table 接成同一條同步交易。呼叫者提供完整 downstream `EP_BRIDGE_CONFIG`、明確的容量契約、replication callbacks，以及逐玩家 array membership callback。缺少 native player creation、allocator 或容量時初始化拒絕；不會採用 legacy harness 的預設十六槽設定。

使用順序是 `ep_replication_bridge_init`、`ep_bridge_preflight(&adapter.admission)`，再使用現有 `ep_bridge_admit/depart/reconnect/retry_cleanup`。完成全部清理後呼叫 `ep_replication_bridge_destroy`。adapter 和 callbacks 的記憶體由呼叫者持有，所有生命週期操作必須序列化。

- 加入依序完成 native confirm、replication append、native player create、replication confirm，最後才發布 admission confirmed。
- 退出先移除 replication，再移除 native player，最後釋放 Session/Party index。replication 和 native cleanup 任一步失敗，既有 bridge cleanup record 會保留 index 與 owner lease。
- append／confirm 自身回滾失敗時，adapter 保存真正的 replication token，透過 `ep_cr_retry_rollback` 收尾。admission generation 和 replication generation 分開保存，不能互換。
- index release 重試不重複執行成功的 remove；舊 admission token 不能刪除重連後的新玩家。逐玩家 membership 不會根據 index 猜測。

`build_x64.bat` 同時建置 `ep_replication_bridge.dll` 和整合測試。測試實際串接 admission、client adapter、client sidecar、replication table，覆蓋 4／8／16 槽、超額拒絕、稀疏 index、退出／重連、partial callback failure、回滾失敗後重試、lease 阻止刪除、native remove／index release 分階段重試。native 和 replication 的末端 callbacks 使用隔離 fixture；沒有遊戲程序或網路封包。

OfficialPlugin 也編入並匯出 init／destroy，提供後續 native provider 的接入點。這個連接只完成本機 callback 協調，尚未實作遊戲網路傳輸或綁定 HD2 的真實 admission／entity callbacks。

另外以 `PlayerResource/ep_resource_bridge_adapter` 作為 downstream provider 完成一組跨元件離線測試：同一筆加入依序進入 resource metadata／三階段 callback、native player、replication append／confirm；退出時 resource、replication、native player 和 allocator index 全部清理。八槽上限拒絕第九人，洞位重連更新 generation，resource stage 失敗不留下 inflight lease。這仍然是 caller-owned synthetic provider，不代表已綁定遊戲的真实资源或 entity ABI。
