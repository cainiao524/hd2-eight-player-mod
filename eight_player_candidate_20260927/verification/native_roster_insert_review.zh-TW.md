# 四插入候選：審查與驗證紀錄

## 固定交付

- [Emitter](../Native/roster_insert.py) SHA-256：`b7bfcd2184382925b4abade40c5e81f21fcdd689f1aea47a2546c055f0bbf551`。
- [Test source](../tests/test_native_roster_insert.py) SHA-256：`7763f5d6664d653816f2b9ec411ec8a8ff942bf45ca1795448f1a130549e7a64`。
- [Test report](native_roster_insert_tests.json) SHA-256：`f2c4ffc2df9a59ccff57bd449945fb5257678c27e7e92e13bae63a3afeba69af`。
- [Evidence](../../five_player_feasibility_20260927/roster_insert_native_evidence.json) 與 recheck SHA-256：`794c357a56b2aa28cfd1061374afe27c1a3a2c06d31ce4ca736e4b783e41b497`。

前一輪已核合的八個 candidate source 未修改。主代理完成新 emitter、bundle 與指令測試；證據代理由固定 capture 重建完整四 body 和 map helper；另一代理獨立審查初始化／caller 前提與 emitter，不修改檔案，也不重跑 Unicorn。

## 獨立靜態核合

審查者以 Capstone 從原 187 條指令獨立核對：56 處 array operands、16 個原 branch／call 目標、4 個 RIP 引用、4 處容量比較，其餘 107 條指令 bytes 保留。四個輸出大小依序為 dense legacy 597、append legacy 502、append registered 505、dense registered 596 bytes。

確認 entry guard 在 prologue 前且無寫入；保留各種 entity／flags ABI；T<8 避免回繞；dense 的 D!=T 拒絕使用正確比較旗標。R11 在四個原 body 無活值衝突，MOV 不改 flags；REX.B／X 選擇與 aux byte store 尾端立即數保留正確。每個原分支落在新指令的前置 R11 load 之前；mover 指向共同候選，map call／tail-jump 指向保存的 helper。有限 range checks 未發現具體阻塞問題。

這是完整本地 body 的靜態審查，不證明真實 dispatch、所有 caller、全域 aliases 或 Windows unwind。

## 指令測試與兩個串接情境

原始測試啟動時因 evidence 代理完成 schema 新增 `bytes_hex`、指紋更新而停止於 SHA 檢查，尚未执行案例；確認最終 evidence／recheck 相同後更新 pin。沒有遊戲程式失敗或通過結果被忽略。

第一批 7 方法／494 次執行通過；追加持續名冊與 property 串接兩項必要驗證後，正式 [9 方法／515 次報告](native_roster_insert_tests.json)全部通過。

| 類別 | 次數 |
|---|---:|
| Append 所有合法分段，八格候選及四格原碼 | 280 |
| Dense prefix／flags 路徑，八格候選及四格原碼 | 184 |
| 非零 flags／第二 ASLR | 4 |
| 四種 ABI 的 binding／count／pending 拒絕 | 22 |
| Reject rel32 範圍兩端 | 4 |
| 兩種 append 持續八筆，再拒絕第九筆 | 18 |
| Append → producer → receiver | 3 |
| 合計 | 515 |

每筆有效插入使用獨立 whole-page oracle：完整 record bytes、原 inline 儲存保持、各計數、map key／ordinal、property 保留與非揮發 GPR／XMM／stack。記錄實際進入 mover／map helper 時的 counts，核對不同路徑的副作用順序。所有原碼對照只用真實四格布局，沒有擴大原 inline 陣列冒充安全八格。

八筆持續情境在同一 Unicorn instance 重複執行，不會每次重設名冊；每一步獨立更新 expected bytes，最後拒絕第九筆，已插入記錄保持。這只證合成 records，未涉及帳號。

Property 串接先由插入 code 與實際 map helper 建立 ID17→7，再讓 producer 自行查 map；producer 沿用前一 suite 的固定八 field／descriptor oracle，最後 receiver 也用 entity ID 查新表。Allocator 是成功契約、incoming bytes 人工提供，沒有實際 serializer／transport。

獨立測試審查確認上述 whole-page oracle 與兩個串接情境，未發現假放行成功的具體缺陷；同時指出 receiver 階段的 helper 呼叫數沿用 producer 累計。已在 receiver 前清空這兩項並加入零呼叫斷言，重跑仍為 9 方法／515 次全部通過。正式報告的 receiver allocator／index-leaf 計數均為 0；此修正沒有更動 emitter。

## 保留限制

1. **Dense D==T 是候選拒絕條件，真實 caller 不變量尚未證明。** 待整理尾端仍須由完整壓實／生命週期處理。
2. Map/new key/empty bucket、有效 entity／flag pointers 與同步是外部前提。原 helper 的重複 ID、滿表與零容量失敗沒有新增恢復。
3. Append／dense 各增 T，不能擅自串作同一次加入；四入口都不完成後續 property／角色／網路階段。
4. Seven-function bundle 的範圍檢查只限已知區域及 reject 入口一 byte，不證明完整 handler 大小、實際配置或地址可用。
5. 初始化／發布／清理、其餘 readers／分類／移除、同步、reject handler、unwind、hook、遊戲與多人驗收仍未完成。

此有限成果可納入 `0.7.0-offline`；三個完成旗標維持 false。
