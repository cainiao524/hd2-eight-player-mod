# 保存證據索引 — 2026-10-19

最新接手入口為 [CURRENT.zh-TW.md](CURRENT.zh-TW.md)。下表連到倉庫內的原始 bytes；完整檔案清單、大小及 SHA-256 由 `SNAPSHOT_SHA256.json` 記錄。

本次只整理已保存在工作區的資料。原始收據中的安裝路徑、程序位址及來源會話路徑屬歷史 metadata；重播不需要存取那些外部路徑。`20261111` 等檔名標籤保留，不覆寫收據內的實際日期。

| 證據 | 檔案 | 用途與限制 |
|---|---|---|
| 完整門檻缺口 | [completion_audit_20261111_r12.json](../output/native_dispatch_20261010/completion_audit_20261111_r12.json) | 所有可玩／發布門檻仍為 false；不是本次重跑的遊戲驗收。 |
| 生命週期缺口 | [party_session_lifecycle_gap_matrix_20261011.json](../output/native_dispatch_20261010/party_session_lifecycle_gap_matrix_20261011.json) | provider、session、roster、mission 及 cleanup 待補項。 |
| 歷史完整離線測試 | [full_offline_test_receipt_20261011.json](../output/native_dispatch_20261010/full_offline_test_receipt_20261011.json) | 469 tests／3752 subtests，包含 native 診斷；歷史結果。 |
| 歷史限定測試 | [offline_candidate_test_receipt_20261011.json](../output/native_dispatch_20261010/offline_candidate_test_receipt_20261011.json) | 54 tests／7 subtests 的原始範圍與指紋。 |
| v2 固定清單 | [party_capture_plan_v2_20261015.json](../output/native_dispatch_20261010/party_capture_plan_v2_20261015.json) | 47,894-byte 最多讀取量與 64 KiB 上限。 |
| v2 採樣原始收據 | [party_capture_authorized_20261016_pid30776_01.json](../output/native_dispatch_20261010/party_capture_authorized_20261016_pid30776_01.json) | 一次授權已使用；84 筆、47,894 bytes；PID 與絕對位址是歷史值。 |
| v2 保存結果分析 | [party_capture_analysis_20261016_pid30776_01.json](../output/native_dispatch_20261010/party_capture_analysis_20261016_pid30776_01.json) | 已讀欄位關係，不代表 owner lifetime。 |
| 六入口初版解碼 | [party_entry_decode_20261016.json](../output/native_dispatch_20261010/party_entry_decode_20261016.json) | 六個 PartyWin RVA；四個命名 export。 |
| 最新呼叫邊界 | [party_entry_call_boundary_20261016.json](../output/native_dispatch_20261010/party_entry_call_boundary_20261016.json) | 拒絕簡單 JMP RAX 模型；實際 dispatcher 未執行。 |
| 邊界測試收據 | [party_entry_call_boundary_tests_20261016.xml](../output/native_dispatch_20261010/party_entry_call_boundary_tests_20261016.xml) | 13 項通過，必須連同診斷日誌解讀。 |
| 邊界測試完整日誌 | [party_entry_call_boundary_tests_20261016.log](../output/native_dispatch_20261010/party_entry_call_boundary_tests_20261016.log) | 保留 21 筆 Unicorn mem_map access-violation 診斷。 |
| 待授權補充清單 | [party_dispatcher_supplement_plan_20261016.json](../output/native_dispatch_20261010/party_dispatcher_supplement_plan_20261016.json) | 16 筆／33,018 bytes；未執行；硬上限 65,536 bytes。 |
| 補充工具歷史測試 | [party_dispatcher_supplement_offline_tests_20261016.xml](../output/native_dispatch_20261010/party_dispatcher_supplement_offline_tests_20261016.xml) | 18 項假讀取器／PE 測試，沒有遊戲存取。 |
| v2 工具歷史測試 | [party_capture_offline_tests_20261015.xml](../output/native_dispatch_20261010/party_capture_offline_tests_20261015.xml) | 45 項離線測試。 |
| C handle ABI 記錄 | [partywin_c_handle_abi_20261015.json](../output/native_dispatch_20261010/partywin_c_handle_abi_20261015.json) | 固定 PartyWin 指紋；不能由名稱推定完整 binding。 |
| 選定 exports | [partywin_export_verification_20261011.json](../output/native_dispatch_20261010/partywin_export_verification_20261011.json) | 未涵蓋兩個未命名 RVA，不猜最近 export。 |
| r5 原始來源 | [live_party_jump_chains_20261111_pid38492_r5.json](../output/native_dispatch_20261010/live_party_jump_chains_20261111_pid38492_r5.json) | 重播 helper 與程式碼來源，固定 SHA-256。 |
| r13 原始來源 | [live_party_api_pointer_probe_20261011_r13.json](../output/native_dispatch_20261010/live_party_api_pointer_probe_20261011_r13.json) | 恢復視窗的地址／指紋基準。 |
| 舊槽來源 | [live_party_slots_external_capture_20261111_pid38492.json](../output/native_dispatch_20261010/live_party_slots_external_capture_20261111_pid38492.json) | 假讀取器使用的既有固定資料。 |
| 十二視窗清單 | [recovered_party_windows_20261015/manifest.json](../output/native_dispatch_20261010/recovered_party_windows_20261015/manifest.json) | 12 × 4096 bytes 與原始來源指紋。 |
| 十二視窗分析 | [recovered_party_windows_20261015/prefix_analysis.json](../output/native_dispatch_20261010/recovered_party_windows_20261015/prefix_analysis.json) | 只覆蓋保存範圍，不包含共同跳轉目的地。 |

## 本次交接驗證

- [VALIDATION_20261019.json](VALIDATION_20261019.json)：本次離線執行、固定指紋和文件檢查結果。
- [SAMPLER_TESTS_20261019.xml](SAMPLER_TESTS_20261019.xml)：本次 63 項離線測試的 XML 收據。
- [CLEAN_SNAPSHOT_TESTS_20261019.xml](CLEAN_SNAPSHOT_TESTS_20261019.xml)：僅含待上傳檔案的獨立副本，在新建環境中再次通過相同 63 項測試。
- [UPLOAD_STATUS.json](UPLOAD_STATUS.json)：遠端核對後的資料提交、tree 和上傳結果。

## 保存與排除範圍

此目錄的頂層研究 JSON／XML、選定測試日誌及 recovered_party_windows_20261015 子目錄納入本次 Git 快照。其他舊 JSON 保留作研究沿革；最新結論從上表進入。探針安裝 ZIP／patch 檔、obsolete build、臨時檢查輸出不新增入庫。

十二視窗的 `.bin` 與兩份保存 probe log 原樣保留，供固定 SHA-256 核對；沒有新增遊戲擷取。未保存的 dispatcher 指令、完整遊戲映像與尚待實測的多人證據，不以空檔或合成結果替代。
