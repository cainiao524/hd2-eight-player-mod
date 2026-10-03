# Client confirmed-peer replication sidecar 契約（build 25480438）

這份 sidecar 是離線、caller-owned 的資料契約。它不尋找遊戲程序、不載入 `game.dll`、不注入、不改寫原生指令，也不聲稱已完成八人聯機。它只在收到已核對的 network index、peer identity、resource handle 和 callback 結果後管理一份可回滾的八槽模型。

## 契約內容

- network index 只能是 `0..7`。Session／Party 分配出的 index 必須由呼叫者原值傳入 `ep_cr_append`；sidecar 不會把洞位壓成另一個 index。
- 五組已核對的 client fixed-four 陣列以獨立 ordinal view 表示：`adjacent_8`、`adjacent_16`、`adjacent_16b`、`confirmed_32` 和 peer-keyed search。每組都有自己的 count 和 `ordinal_to_index`。移除時只壓實該組 ordinal，其他組和穩定 network index 不變。
- `array_membership_mask` 必須明確包含 `confirmed_32`；peer-keyed `+0x150` 不會被推定與 confirmed-peer 一對一。
- append、confirm、remove、kicked、reset 都必須先經 callback。callback 使用完整五組 mask；callback 失敗會回滾，回滾 callback 也失敗時保留 `ROLLBACK` 槽位和 token，必須用 `ep_cr_retry_rollback` 收尾。
- generation 與 network index 綁定。離隊後的洞位可重用但 generation 增加，舊 token 永遠不能移除重連玩家。
- callback lease 以槽位保存。lease 未離開時拒絕 remove/kick/reset；migration 也必須等待所有 lease、pending 和 rollback 清空。
- host migration 是 begin／commit／abort 交易，owner key 與 epoch 只有 commit 才更新；epoch 必須遞增。
- 所有 mutex、callback 和 invariant 異常都 fail-closed。`ep_cr_production_enabled()` 固定回傳 `0`，所以這份 artifact 不能直接當作遊戲插件。

## 離線驗證

```powershell
cmd /c build_x64.bat
```

合成測試涵蓋八個 stable index、index 8 拒絕、洞位與 ordinal compaction、generation fence、五組 mask、callback failure compensation、rollback retry、callback lease/quiescence、kicked/reset、host migration 交易和 production gate。測試只載入本目錄剛編譯的隔離 DLL。

## 尚未證明的原生條件

目前資料沒有確認 client confirmed-peer native callback 的 register／return／cleanup ABI，也沒有證明 `player index` 語義、原生 entity 建立、資源生命週期、PlayFab／Party admission 或第五至第八帳號的 peer/entity replication。這些缺口關閉前，production、installable 和 multiplayer gates 都保持 false。
