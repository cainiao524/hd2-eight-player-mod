# 二進位 snapshot 候選：審查與處理

## 範圍

本輪由主代理實作與測試，另由 `/root/web_research` 代理完成只讀語義審查。該代理未編輯檔案、未執行候選或遊戲；實際 LuaJIT 測試由主代理執行。先前其他支線的代理受用量限制，不影響本文件所記錄的這次審查已完成事實。

審查對象為 `pool_snapshot.lua`、`pool_preflight.lua` 與已固定的 `indexed_float_subobjects_evidence.json`／findings。完整 API 與未閉合事項見[資料契約](../SNAPSHOT_CONTRACT.zh-TW.md)。最終來源 SHA 與測試環境記錄於[測試報告](pool_snapshot_tests.json)，交付版本以該報告及 [manifest](../candidate-manifest.json) 為準。

## 發現與處理

| 發現 | 處理與結果 |
|---|---|
| 原 snapshot validator 只要求 free node 的 `N+20` template pointer 為零，可漏過其餘非零 payload | 新增 regression，先重現七個偽通過案例，再比較完整 `0x208` bytes 的兩種已知模式；修正後通過。保留[修正前失敗摘要](pool_snapshot_before_free_node_fix.json)，其 source SHA 是舊版，不是最終交付。 |
| 最初審查建議 free node 全零，但 constructor 清零後的 reset 會寫入兩個 1.0f | 主代理指出 `1408FE9/1408FF3`，審查代理接續核對完整 constructor／reset／cleanup 鏈；修正採全零或僅 `A8/AC=1.0f` 的雙模式。 |
| 未提供 S 認領的 occupied node 可以保留，不能把它當成完整全池所有權證明 | 保留此設計，因計算批次需求時必須包含其他占用；audit 記錄 unclaimed 數。文件明示 `all_occupied_nodes_accounted` 也不能排除未提供舊副本／外部 aliases；所有輸出 `executable=false`。 |
| packet 自帶版本及模板內容沒有來源真實性 | 保留作提供資料的結構檢查，文件與結果範圍明示來源仍待可信 adapter 驗證。未把 target 指紋複製值當成 live 驗證。 |
| preflight 在空間不足後仍輸出假設完整配置的 final state，可能被誤用為原生 partial 狀態 | 新增 `state_semantics="full_allocation_plan_not_native_post_state"`；README／契約明示 steps 與 final 欄位不可用於覆寫實際恢復狀態。原算術及操作順序不變。 |

## 雙模式的保存指令依據

來源 SHA-256：`5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54`。

- `142BAC6` 建立 nodes base `D+3718`；`142BAE3` 指定 `0x100` 次迴圈。
- `142BB40..142BB4B` 對 N 呼叫 byte-fill helper 清 `0x208` bytes，`142BB50..142BB53` 隨後呼叫 `1408FE0`。
- `1408FE9/1408FF3` 無條件寫 `N+A8`、`N+AC` 為 `0x3F800000`。已清零的 `N+28` type=0，略過 type 1..4 payload 分支；`14090A5..14090B4` 清 `N+B0` 起 `0x140` bytes，`14090B9` 清 `N+200` byte。
- Cleanup 的 `140C238` 呼叫 `1408F00`；後者在 `1408F7A..1408F8A` 以 zero fill、長度 `0x208` tail-call 清整個 N。返回後 `140C248..140C252` 才清 occupancy。
- 配置路徑在 `140C39C` 先設 occupancy=1，之後 `140C40C` 才呼叫 reset；不形成第三種已證的穩定 free 模式。

審查代理在上述保存指令範圍內未找到其他穩定模式。Constructor 兩個 DWORD store 之間，可能看到僅 A8=1.0f 的瞬時狀態；候選會保守拒絕它。這不是已取得原子 snapshot 的證明，仍需要相同執行保護。

## 驗證結果與未涵蓋範圍

[測試程式](../tests/test_pool_snapshot.py) 以 Python `struct` 建立合成資料，透過 `lupa.luajit21` 直接執行兩份實際 Lua source。最終新增 20 組測試通過，原 preflight 11 組測試亦通過；report 記錄來源與三份依據的 SHA-256。測試不是原生指令執行，也不是遊戲 heap capture。

這次審查與測試沒有證明資料取得的原子性、完整 aliases、外部 resource handles、原生配置／釋放成功，或任何五至八人連線結果。沒有修改或安裝遊戲檔案。
