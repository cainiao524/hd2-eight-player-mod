# Roster getter 原生測試獨立核對

2026-09-27；只讀審查 `tests/test_native_roster_getter.py` 與 `verification/native_roster_getter_tests.json`。未修改 getter source、測試或測試報告，亦未重跑其他 suite。

## 結論與固定指紋

最後版未發現阻擋性的局部 oracle 或報告缺陷。7 個方法、84 次 Unicorn x64 執行，0 failure、0 error；候選 73 次、原版普通 baseline 10 次、原版 empty-key stale-value 預期 phantom hit 1 次，分類相加與 `emulator_runs` 長度同為 84。測試、pin 的 classifier fixture、9 份 Native source、7 份 evidence 的報告 SHA 均與現有檔案相符。

- 測試 SHA-256：`f14f3b4a314e6a92ce7dea01d7e5e37b457ef7d2a2538f80a029c9dc7e86aa13`
- 報告 SHA-256：`8080ef58bd25d7c71bf5e5a9a6a89386a1bd50c6b466004c8388b9043832d239`
- Getter source SHA-256：`3de7432a9c1218ab98f2e92679583cb299c93d4ba8bcb739fea8aa980520ef5d`
- Getter evidence SHA-256：`1360863bfe1f1f6ce640ef049776d3b31703a1cbfe2bea3f90bf20555f69e0fd`
- Classifier fixture SHA-256：`50ac149e11274994f4f8fa6e766e5937ff1317130eb1a16718882da7859a8593`

## Oracle 覆蓋

- `success()` 比對完整 zero-extended `RAX`，並對 hit 斷言恰有目標 property `+0Ch` 的 4-byte 讀取；miss 則要求完全沒有 property 讀取。所有 getter case 都檢查非 stack 頁面逐 byte 不變、非揮發 GPR／XMM 與 EDX ID 保留，執行期寫入只在 stack。
- 已覆蓋八個 map ordinal，包括全 pending 分區；6 種 network DWORD 值（含 `0`、`7`、`8`、`80000000h`、`FFFFFFFFh`）不被當作 ordinal 或截成小範圍。另測 capacity `1/2/4/8/16` 的有效 power-of-two map、不同 hash home、multiplier 3 與第二 ASLR；四格原 body 與候選配對回傳值。
- 普通 invalid ID、capacity 0、滿表／非滿表 miss、map ordinal `FFFFFFFFh` 均回傳 `FFFFFFFFh` 且不讀 property。候選在錯 S binding、ordinal／tracked count 非法、查得舊 empty-key bucket value 等情形明確 reject，要求 reason、無 property 讀取與無非 stack mutation。原版 empty-key stale-value 可能讀到假的 property hit，被單列為**原版預期反例**，沒有混進普通 baseline。
- 串接測試載入 SHA pin 的 classifier fixture；該段暫存配置／釋放仍使用已聲明的契約 stub。分類後 ID67 在 slot 2，getter 回傳 `FEDCBA98h`。接著真的執行保存的 map-delete `172F8A0` body 與 emitted mover，trace 順序為 delete、mover、mover；以完整非 stack page oracle 驗 count、map 與四組記錄。刪除 ID19 後 ID67 移至 slot 1，getter 仍回傳 `FEDCBA98h`；ID27 在 slot 2 正常讀取，已刪 ID19 回傳 missing 且沒有 property 讀取。報告 chain metadata 的 T/D/P、實際 ordinal、query 與 component 與這些狀態一致。

## 界限

fixture 是合成 RAM，前提為有效可讀 map、零或二次方容量及正確 probe chain；不測 malformed map allocation。分類鏈的暫存 helper 是契約 stub，remove 階段則執行固定 map-delete 與 mover 機器碼。本證據不證實真實 caller 生命週期、同步、reject continuation、Windows unwind、hook 安裝或多人執行；報告的 `fixture_synthetic=true`、`game_process_accessed=false`、`host_native_code_executed=false`、`installable=false` 與此範圍一致。
