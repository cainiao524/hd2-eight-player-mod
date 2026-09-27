# Roster classify 原生測試獨立核對

2026-09-27；只讀檢查 `tests/test_native_roster_classify.py` 與 `verification/native_roster_classify_tests.json` 的 oracle、固定指紋及執行分類，未修改候選 source、測試或測試報告，亦未重跑其他 suite。

## 結論

最後版未發現阻擋性的局部測試或報告缺陷。報告為 7 個方法、853 次 Unicorn x64 模擬執行，0 failure、0 error；候選 783 次、原四格 baseline 70 次，總數與 `emulator_runs` 長度一致。測試檔、8 份 Native source、6 份固定 evidence 的報告雜湊均與現存檔案相符。測試使用明確的暫存 helper **契約 stub**；沒有執行真實 allocator／release body。

## Oracle 覆蓋

- `test_02` 在八格 `T=1..8`、`P<=D<=T` 的所有合法分類方向及 ordinal，執行 660 次候選；`success()` 用獨立的邊界交換模型比對四陣列全部記錄 bytes、非目標尾端資料、P 計數、map 兩筆 ordinal 及線性探測可達性。相等邊界路徑要求沒有 helper call。
- 移入方向明確保留 source ordinal 的 primary 70h 原 bytes，只將邊界 primary 70h 清零；移出方向對四陣列作完整交換。整頁 byte oracle 會擋下把兩方向錯實作成同一 swap 的回歸。
- `test_03` 在原生四格資料布局執行 70 次原 body，逐組與候選配對四陣列、map 及 `RAX`；`test_04` 使用第二 ASLR 與 multiplier 3 驗證不同 hash home、非對稱 primary 保留。
- 暫存 stub 核對 create／allocate／release／release 的順序、70h／38h／20h size、alignment 4、Win64 call alignment 與 32-byte shadow space、24-byte context C 及 alloc `RCX=C[0]=A`。它 clobber volatile GPR／XMM0..5；第一次 release 後即禁止再觸碰暫存 buffer，第二次 release 後保持原 arena block／offset。非揮發 GPR／XMM6..15 於返回後受檢。
- `rejected()` 對無效 count、方向、map key／ordinal／capacity、binding、flag、pointer 和 rel32 邊界，要求 reason、無 helper call、非 stack 頁面逐 byte 不變、所有被觀測執行期寫入留在 stack。新增 `P=0` 移出與 `P=D` 移入拒絕，覆蓋已知下溢／過界方向。
- 串接測試連續移入 key67、59，再移出 key67、11；最後 key67 位於非零 ordinal 3。receiver 以 key67 實際讀 map header／bucket，寫 property slot 3，wire network word 仍為 7；map 的 bijection／probeability 維持成立。

## 界限

fixture 使用合成、唯一 ID 且有效 partition 的 RAM；entity flag 由合成 caller staging。三個暫存 helper 是遵守已固定呼叫協定的 stub，假設 allocation 非 null、release 可正常恢復且沒有交錯；沒有證明真實 helper 的失敗回復、並發資源 ownership、外層 caller 通知、Windows unwind、安裝或多人執行。原 body 在第一次 allocator 呼叫前已改動共享 roster，測試沒有聲稱 allocation failure 原子性。報告的 `fixture_synthetic=true`、`game_process_accessed=false`、`host_native_code_executed=false`、`installable=false` 與此界限相符。

## 固定指紋

- 測試 SHA-256：`50ac149e11274994f4f8fa6e766e5937ff1317130eb1a16718882da7859a8593`
- 報告 SHA-256：`aa444e55a0f9b0df94fbf79a4bbbb87ef62d173b809c9c80748380ef2d82687e`
- Classify source SHA-256：`bc4508fadf17726b773ed9c4237f7693405856ccc0b57ddcac4d06e073f46153`
- Classify evidence SHA-256：`f20165dad6823edc40fbcdf0434123139f1c80d9222a2b20d3f4c067768e9e33`
