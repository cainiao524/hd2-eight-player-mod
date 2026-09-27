# 八格名冊：entity ID → network index 原生讀取候選

版本 `0.10.0-offline`。本輪完成原 `606AD0..606B75` 的單一完整 getter，讓名冊分類／移除後的讀取查詢與現有候選使用同一份八格 property。十二函式共同產物只包含離線 bytes 與 metadata；尚未提供可安裝 Mod 或遊戲執行證據。

## 讀取契約

入口 **EDX 是 entity ID 的 32-bit 值**；RCX 不用於選取 roster。原程式透過 global `[game+3326468]` 得到 S，查 S 的 ID→ordinal map，再讀 property 的第四 DWORD。這三個值必須分開：

`entity ID → map ordinal n → property[n].network_index`

候選將唯一的原讀取 `[S+3B4h+n*20h]` 改為 `[B+58Ch+n*20h]`。B 是既有 `680h` 四陣列 sidecar，property 起點 B+580h，欄位位移 Ch。返回 EAX 是完整原 DWORD，RAX 上半部為零；不把 network index 改成 ordinal，也不截成 0..7。

原 getter 不讀 P／D／T。新讀取 guard 使用 tracked count T，不用 dense D，因此 **已存在且有效的 pending 記錄也可以讀取**。整份 map／property 有效性、同步及初始化依然是外部前提。

## 保留的正常 missing 路徑

下列原路徑維持 RAX=`00000000FFFFFFFF`：

- 輸入 ID 等於 global invalid sentinel `[game+3483C20]`。
- map capacity 為 0。
- 遇到 empty bucket，且該 key 不等於輸入 ID。
- 最多探測 capacity 個 bucket 後仍找不到。
- 命中 bucket 的 ordinal 是 `FFFFFFFFh`。

Global invalid ID 的分支先於新 binding guard。即使 global S 值未映射，該原路徑也不解參 S／map。其他請求若 binding 不合，會先拒絕，不再查錯誤 roster 是否有該 ID。

Getter 保留原 capacity−1 mask 與有界探測，不把 capacity 強制改成 8；capacity 0 及有效的 power-of-two map 語義不變。共同候選中的其他 writer 各自保留其容量契約，這個 reader 不擴大那些 writer 的支援範圍。

## 新增拒絕策略

| Reason | 檢查時點 | 條件 |
| --- | --- | --- |
| 1 | `606AF3`，global-invalid 分支後、首次 S 解參前 | global S 與指定 roster 不同 |
| 2 | `606B67`，成功 lookup 後、property 讀取前 | ordinal ≥ 8 |
| 3 | 同上 | tracked T > 8 |
| 4 | 同上 | ordinal ≥ T，包含 T=0 的 stale hit |
| 5 | 同上 | 輸入 ID 等於 map empty key，且原程式走到可讀取 ordinal 的成功路徑 |

Reason 5 修補一個已核實的邊界：原碼遇 empty bucket 後會再比較它是否等於輸入 ID；若相等且 bucket 留有非 `FFFFFFFF` 的 value，原碼可能讀到不屬於該 ID 的 property。候選拒絕這種假命中；若 value 本來就是 `FFFFFFFF`，仍保留原 missing return。這是新增策略，沒有宣稱原碼已具備。

共同 reject 區先寫 R10D=reason，再從 caller shadow space 恢復 RBX／RBP／RSI／RDI，跳至整合者指定的 reject 入口。RSP 保持入口值，EDX ID 與 nonvolatile GPR／XMM 保留。RAX、RCX、R8、R9、R10、R11、flags 不保證保持原輸入。

整個候選只有原來的 32-byte caller shadow saves，沒有新增 push、helper call 或非 stack 資料寫入。reject handler 尚未實作，不能把它當作可直接安裝的錯誤處理。

## 固定來源與機器碼

- [原始碼](Native/roster_getter.py)以 Python 標準函式庫產生 bytes，固定 evidence 與 body SHA。
- [來源證據](../five_player_feasibility_20260927/roster_getter_native_evidence.json)、[離線重播](../five_player_feasibility_20260927/roster_getter_native_replay.py)、[行為分析](../five_player_feasibility_20260927/roster_getter_native_findings.zh-TW.md)與[前提核對](../five_player_feasibility_20260927/roster_getter_native_prerequisites.zh-TW.md)固定完整 165 bytes／43 條指令，單一 unwind fragment。
- 原 body SHA：`96ce6884140adb9ae93688e042a2b5db7ffc1e59ffb45eb03188e6bab79abcfb`。
- 輸出 **354 bytes／70 條指令**。所有 local branch 與兩個 global RIP 讀取均重定位。
- `606B6B` 之前載入 `R11=B+1D8h`，只將原 operand 的 SIB index 從 R10 改為 R11；原 RAX 已乘 20h，R10 仍是 S。沒有改變成功返回的 DWORD。
- [十二函式共同建置範例](verification/native_roster_getter_bundle_synthetic.json)與[合成地址](verification/native_roster_getter_addresses_synthetic.json)包含同一 S／B、getter 原 body、程式及 reject entry 的有限區域交疊檢查。

支援的保存來源仍是 Windows x64 build 25480438，版本指紋見 [manifest](candidate-manifest.json)。這不是對目前遊戲程序的版本檢查結果。

## 建置

在工作區根目錄執行，輸出路徑需尚不存在：

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 `
  eight_player_candidate_20260927/Native/roster_getter.py `
  --evidence five_player_feasibility_20260927/roster_getter_native_evidence.json `
  --classify-evidence five_player_feasibility_20260927/roster_classify_native_evidence.json `
  --remove-evidence five_player_feasibility_20260927/roster_remove_native_evidence.json `
  --insert-evidence five_player_feasibility_20260927/roster_insert_native_evidence.json `
  --move-evidence five_player_feasibility_20260927/roster_move_native_evidence.json `
  --producer-evidence five_player_feasibility_20260927/roster_property_producer_native_evidence.json `
  --receiver-evidence five_player_feasibility_20260927/roster_property_receive_evidence.json `
  --addresses eight_player_candidate_20260927/verification/native_roster_getter_addresses_synthetic.json `
  --output eight_player_candidate_20260927/verification/native_roster_getter_local.json
```

## 驗證與限制

[7 組測試](verification/native_roster_getter_tests.json)通過 **84 次 x64 執行**：73 次候選／串接、10 次原四格／正常 missing 基準、1 次原 empty-key stale-value 假命中的預期重現。該最後一項不是有效 ID 的相容性成功；候選會在讀 property 前拒絕。

[測試原始碼](tests/test_native_roster_getter.py)驗八個 ordinal、完整 DWORD（含高位及 FFFFFFFF）、pending 讀取、capacity 0／1／2／4／8／16、各 missing 路徑、未映射 S 的 global-invalid 路徑、五種拒絕、ABI／非 stack bytes、ASLR／rel32 及十二函式交疊拒絕。

串接使用固定 SHA 的分類 fixture，只有分類暫存 helper 仍為明示契約 stub。ID 67 先由 ordinal 7 分類移到 2，getter 讀回 `FEDCBA98`；之後實際執行保存的 map-delete 與候選 mover，刪除 ID 19，令 ID 67 移到 1。Getter 仍回同一 DWORD；ID 27 的換位讀取亦正確，被刪 ID 19 回 missing 且不讀 property。串接另以獨立四組 bytes／counts／map oracle 檢查移除結果。

[獨立 source 審查](verification/native_roster_getter_review.zh-TW.md)核完整 43 條原指令、兩組 guard、唯一 property operand、返回／拒絕與已知區域；[獨立 oracle 審查](verification/native_roster_getter_test_review.zh-TW.md)核最終測試與 pins。兩者未發現此有限範圍剩餘阻擋缺陷。共同範例另確認可逐 byte 重建。

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 eight_player_candidate_20260927/tests/test_native_roster_getter.py
```

依賴沿用本候選 `.native-test-deps` 中的 Unicorn 2.1.4／Capstone 5.0.7；沒有執行主機原生 bytes 或遊戲程序。這輪只跑新增 getter 套件，原十一個來源、十套報告及固定分類 fixture 保持指紋。十一套保存結果合計 122 組／3,954 次，其中 3 次是原程式預期反例／假命中；這些數目不代表多人驗收進度。

這個 getter 只完成一個已定位 reader。其他仍讀原內嵌陣列的程式不能與 sidecar 混用。完整 map bijection、有效 property 初始化、生存期／同步、caller hook、Windows unwind、reject handler、sidecar 配置／發布／釋放均未由本函式解決。原整理流程的 pending 所有權問題、平台加入與第五人角色建立也仍是缺口。

下一個必要切點為已定位的 `605950..605F2F` 移除前處理：固定其讀取的關聯 entity ID、其他 roster 陣列／衍生地址及通知次序，再決定如何與既有移除候選接合。限於該完整 body 和已有來源關係，不重新泛掃描。完整八人目標與外部條件見[工作清單](../five_player_feasibility_20260927/IMPLEMENTATION_WORKLIST.zh-TW.md)。
