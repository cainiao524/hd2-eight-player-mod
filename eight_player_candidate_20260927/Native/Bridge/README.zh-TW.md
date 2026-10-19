# Native bridge orchestration candidate

這個目錄把最多十六槽 sidecar 的生命週期與遊戲專用 callback 契約接在一起：

- preflight 先比對 build、模組 site bytes 和三個遊戲 callback 加上 retain/release owner lifetime callback；
- admission 依序 reserve、confirmed-peer callback、player-creation callback、sidecar confirm；只有 native player 建立成功後才發布 confirmed slot；
- admission 先向 caller-provided `allocate_index` 取得 Session/Party 的 authoritative network index，再以 `ep_sidecar_reserve_at` 綁定同一 index；release callback 失敗時保留整個 slot 與 owner lease，禁止用另一個本地空槽替代；
- `ep_bridge_admit_at` 提供建立交易的固定 index 組合入口；allocator 回傳不同 index 時會在 sidecar reservation、native confirm/create 與 replication event 之前拒絕，allocator release 失敗則保留 generation-zero retry record；
- `ep_bridge_client_integration_test.exe` 會把 Native Bridge 和 client adapter 串在一起，驗證 native confirm 失敗時保留補償記錄、由 bridge 呼叫 remove，並同時清掉兩端 sidecar；
- 任一 callback 失敗都嘗試回滾 slot；若遊戲 cleanup callback 失敗，slot 和 owner lease 會保留，必須用 retry cleanup 完成後才釋放；
- authoritative allocator 已分配但 sidecar 尚未建立時，若 `release_index` 失敗，bridge 會保存 generation-zero allocator-only retry record，保留 index、identity 與 owner lease，直到 `ep_bridge_retry_cleanup` 完成；
- departure 先要求 player cleanup callback，再移除 sidecar slot；
- reconnect 保留可用的 network index，並以新 generation 拒絕 stale token；cleanup retry 必須帶完整的 peer、resource handle、index 和 generation，避免延遲 retry 誤刪重用的 slot；
- active capacity 已滿、重複 identity 或缺少 callback 都 fail-closed。未提供
  host contract 的離線 harness 以 16 槽儲存上限啟動；實際遊戲值仍由
  `EP_CAPACITY_CONTRACT` 的 effective capacity 決定。
- 同一個 bridge 同時只允許一筆同步操作；cleanup 未清完時拒絕 destroy，避免重入或 stale handle。

`ep_native_bridge_test.exe` 是合成 harness，會走完十六個 admission、拒絕第十七個、移除孔洞、重新連線及完整清理。`ep_bridge_client_integration_test.exe` 另外驗證跨元件補償與 owner lease 平衡。兩者都沒有尋找、寫入或注入 `game.dll`，callback 也不是遊戲的真實 ABI；因此這個 bridge 目前仍是 candidate，不能稱為已完成多人 Mod。

要成為 production bridge，必須再把 `EP_BRIDGE_CONFIG` 的 callback（包括 authoritative index allocator/release）接到固定 build 的 host/client confirmed-peer、player creation、departure/cleanup 入口，並由 mid-function capacity/allocator stub 提供正確的 register、stack、unwind 和 continuation。所有遊戲 callback 與 owner lifetime 接通前，Package gate 應保持 blocked。

## Allocator error compensation（2026-10-04）

Bridge 現在保留 allocator callback 在錯誤返回時寫入的非 `0xFF` index，並把它交給 generation-zero release/retry。Client adapter 對 `index >= 16` 保存獨立 allocator-only reservation；對已存在的 0..15 reservation 則使用 `0xFF` no-reservation sentinel，不會釋放原玩家的 index。

跨元件合成測試覆蓋越界 index 立即補償、release 失敗後 retry，以及已保留 index collision；這仍是 callback-shaped 離線測試，沒有連接真實 Session/Party allocator。
