# Producer 與共同建置候選：審查及驗證範圍

## 來源與指令審查

Emitter 作者 `web_research` 固定完整 `60C640..60C882`，製作 662-byte producer 候選。主代理從原 capture 獨立核對 578 bytes／130 指令、unwind 範圍、wrapper bytes／call 與正常 CFG，確認 `60C6C9` 是 allocator 與八個 property stores 的必經位置；[核對記錄](../../five_player_feasibility_20260927/roster_property_producer_native_review_checks.json)保留這個範圍。

另一代理 `pool_double_records` 從原 capture 再核完整 body，以 Capstone 重算四個外部參照，確認輸出原 body 只改四個 relocation 與五-byte splice。RBP 偏置後的記憶體目的地恰為八個 property stores，包括 `C7FF→C803→C807` 的衍生地址；保存的 `134F190` leaf 共 22 指令、無 call、未改 R11。未發現阻止採納此局部候選的問題。

## 獨立執行測試

主代理獨立於 emitter 作者撰寫 [producer 測試](../tests/test_native_roster_producer.py)，直接執行原碼、產生碼與保存 index leaf。**10 組測試／54 次隔離 x64 執行全部通過**。記憶體變更與順序、原版對照、八個 ordinal、不同 network index、查表／拒絕、呼叫 ABI、四個 relocation 的可達邊界及 producer→receiver 資料橋均納入測試。

Allocator 使用明確成功契約 hook：檢查 object／size32／alignment4／stack alignment，破壞 volatile GPR／XMM 後回傳合成 buffer。這沒有驗證真實 allocator 的失敗、回收或外部資源。橋接按 descriptor pointers 拼接八個值後交給 receiver；它沒有執行遊戲 serializer、dispatch、transport 或多人同步。Reject 停在指定入口，保留 interior frame，沒有偽造返回。

`pool_double_records` 逐讀此測試與限制，核對 source／test／report 指紋；未重跑或擴充測試。原 source、固定 evidence 與既有 receiver 未在測試期間改動。

## 共同建置審查

主代理新增 [pair builder](../Native/roster_property_pair.py)及 [4 組組合測試](../tests/test_native_roster_pair.py)。它強制共用同一 S/B，要求兩個不同 frame 的 reject entry 分開，並驗有限已知區域的交疊；測試確認跨程式、reject、原碼與 global 碰撞被拒絕，個別 emitter 的輸出保持一致。

`web_research` 唯讀審查 pair 與四組測試，未見實質局部缺陷。它指出測試註解原稱「恰好相接」並不精確：662-byte producer 與下一個 16-byte 對齊起點相隔 10 bytes。主代理修正註解並重跑四組，全部通過；程式邏輯未因此改變。

## 可核對檔案

| 檔案 | SHA-256 |
|---|---|
| Native/roster_producer.py | `015b2240847019bfb62fa62a72ce8af93894f2d61b0369d5079aa40d40697a4b` |
| Native/roster_property_pair.py | `5828d6a03bfce89ea63e3c8e8c49bca60825aa8b11533dd7e545570f183dba63` |
| tests/test_native_roster_producer.py | `68b6d7573c219a977903e345e67fa24792e852ef234392da12c4f4ad312e7fe7` |
| tests/test_native_roster_pair.py | `b9fb2e2b4ed8251eb50d74b4488aa7423f68996b0921e2eabf3ee7861cc25d11` |
| verification/native_roster_producer_tests.json | `3176b9e9e5b4cd59ca609fe810f6d3cc69e208a56991d4ee7d1b08370203a642` |
| verification/native_roster_pair_tests.json | `1a2375fe596e1e21a5875e625837a5218446b805205e7cb95e44e04702621c0e` |

## 仍未驗證的完整整合

有效 entity／map／輸出容量、指標來源與物件世代、所有讀寫者的共同改接、儲存建立與釋放、同步／重入、真實 allocator 與 helper 執行條件、Windows unwind、拒絕後整次操作的恢復，以及 hook 安裝／移除均未完成。有限 range 檢查不等於完整程序配置圖；reject handler 只列入口一 byte，完整長度仍須外層驗證。

本局部來源與指令執行停止條件已達成。下一步沿[有限清單](../../five_player_feasibility_20260927/roster_property_consumers_native_findings.zh-TW.md)實作搬移與平行陣列，不以增加同型測例代替實際整合。候選維持 `installable=false`、`game_execution=false`、`multiplayer_verified=false`。
