# Native bridge orchestration candidate

這個目錄把八槽 sidecar 的生命週期與遊戲專用 callback 契約接在一起：

- preflight 先比對 build、模組 site bytes 和三個遊戲 callback 加上 retain/release owner lifetime callback；
- admission 依序 reserve、confirmed-peer callback、sidecar confirm、player-creation callback；
- 任一 callback 失敗都嘗試回滾 slot；若遊戲 cleanup callback 失敗，slot 和 owner lease 會保留，必須用 retry cleanup 完成後才釋放；
- departure 先要求 player cleanup callback，再移除 sidecar slot；
- reconnect 保留可用的 network index，並以新 generation 拒絕 stale token；
- 八槽已滿、第九個玩家、重複 identity 或缺少 callback 都 fail-closed。
- 同一個 bridge 同時只允許一筆同步操作；cleanup 未清完時拒絕 destroy，避免重入或 stale handle。

`ep_native_bridge_test.exe` 是合成 harness，會走完八個 admission、拒絕第九個、移除第 5 格、重新連線及完整清理。它沒有尋找、寫入或注入 `game.dll`，callback 也不是遊戲的真實 ABI；因此這個 bridge 目前仍是 candidate，不能稱為已完成多人 Mod。

要成為 production bridge，必須再把 `EP_BRIDGE_CONFIG` 的 callback 接到固定 build 的 host/client confirmed-peer、player creation、departure/cleanup 入口，並由 mid-function capacity/allocator stub 提供正確的 register、stack、unwind 和 continuation。所有遊戲 callback 與 owner lifetime 接通前，Package gate 應保持 blocked。
