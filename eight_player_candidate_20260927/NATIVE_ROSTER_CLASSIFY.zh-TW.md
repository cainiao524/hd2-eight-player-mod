# 八格名冊分類原生候選

版本 `0.9.0-offline`。這是工作區內的 x64 bytes 產生器，尚未安裝或接入 HD2。它將 `60CF50` 移入分類與 `60D300` 移出分類接到既有 `680h` 八格儲存，並與插入、搬移、移除及 property 產生／接收共同建置。平台加入、原生角色建立及真人多人任務尚未驗證。

## 完成的行為與保留的差異

令 S 為原 roster、B 為八格 sidecar，`T=[S+80h]`、`D=[S+84h]`、`P=[S+88h]`；n 為 entity ID 查得的 ordinal。H、T、D、map header 留在 S。兩個入口都以 RDX 傳入 entity，透過 global `[game+3326468]` 取得 S。

| 方向 | 允許的輸入 | 原生行為，候選保留 |
| --- | --- | --- |
| 移入 `enter` | `0≤P≤n<D≤T≤8`，target bit0 已設 | n=P 時 P++、清零 primary[P]。n>P 時交换 pointer／aux／property、清零 primary[P]、primary[n] 留在原位；修正兩筆 map 後 P++ |
| 移出 `leave` | `0≤n<P≤D≤T≤8`，target bit0 尚未清 | n=P−1 時只減少 P。其他情況完整交換四組記錄、修正兩筆 map 後 P-- |

**移入沒有保留每個 entity 的全部 primary bytes。** 這是已保存原指令的行為；非 prefix primary 的有效性及所有權仍需 caller 契約證明。Property 的完整 20h bytes 隨 entity 換位，`+Ch` network index 不會被新 ordinal 取代。

sidecar 布局沿用[共同儲存契約](NATIVE_ROSTER_BUNDLE.zh-TW.md)：pointer B、primary B+40h、aux B+3C0h、property B+580h。原四筆內嵌陣列保持原 bytes；其他尚未改接的 reader 不能與這個候選混用。

## 來源、實作及共同建置

- [原始碼](Native/roster_classify.py)僅使用 Python 標準函式庫；固定 evidence／完整 body SHA，拒絕任意版本輸入。
- [來源證據](../five_player_feasibility_20260927/roster_classify_native_evidence.json)、[重播程式](../five_player_feasibility_20260927/roster_classify_native_replay.py)與[必要前提](../five_player_feasibility_20260927/roster_classify_native_prerequisites.zh-TW.md)固定兩個完整 body 及三個暫存 helper。
- 移入原 934 bytes／197 指令，輸出 1,921 bytes；移出原 1,120 bytes／232 指令，輸出 2,275 bytes。共 88 個直接／衍生 array operands 改接，全部 local branch、兩個 global RIP read 及 helper call 重定位。
- 每個 array operand 以 `push RBP; mov RBP,B−E8h; patched instruction; pop RBP` 局部改接，必要 displacement 加 20h／1E0h／2C0h；下一條原指令前還原 RBP。沒有在暫存 buffer 或 map operand 上套用陣列偏移，也不依賴 R11 已不再使用。
- [十一函式共同範例](verification/native_roster_classify_bundle_synthetic.json)與[合成地址配置](verification/native_roster_classify_addresses_synthetic.json)包含同一 S/B 綁定及有限已知區域碰撞檢查。此前只保留 allocator 入口 1 byte 的範圍，已在這層提升為已保存的完整 386-byte helper。

支援的離線指紋仍是 Windows x64 build 25480438，EXE SHA `f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06`、game.dll SHA `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e`。這些是保存來源的版本，不表示已核對目前執行中的遊戲。

## 前置檢查與拒絕契約

在原 prologue／首次共享資料修改之前進行 bounded map lookup，最多八個 bucket，檢查：

1. global roster 與指定 S 相同。
2. T 為 1..8。
3. `P≤D≤T`。
4. map capacity 為 8。
5. ID 不是 map empty key 或 global invalid sentinel，且存在於 map。
6. n 小於 D。
7. n 在該方向要求的 prefix 內／外。
8. sidecar pointer[n] 指向的 entity ID 符合 map key。
9. 該 entity bit0 為 1。

檢查順序即 reason 1..9。拒絕時 R10D=reason、RSP 恢復入口值，RCX/RDX/R8/R9 與全部 nonvolatile GPR/XMM 保留，RAX/R11/flags 可改變。檢查會使用 56 bytes scratch stack；不寫 roster／sidecar／map／entity。合法路徑的局部 array 改接另暫用 8 bytes stack，立即還原，未改 helper 呼叫對齊及 shadow space。

此 guard 只核 target，**不是完整 map／所有記錄驗證器**。其他 tracked IDs 唯一、map probe chain／bijection、boundary partner 有效及其 ordinal 正確、所有指標可讀寫、有效生存期與同步仍是必要前提。原後置 map lookup 遇空 bucket 或失敗不能安全補 key；不能把 target 查找通過當作所有後置寫入都安全。

reject handler 尚未提供。移入 caller 先設 flag，移出 caller 先派發通知，再進分類 body。因此拒絕只保留本函式入口狀態，**不會回復已發生的 caller flag／通知**；整合者需處理外層操作，不能直接正常 ret 並讓 caller 當作成功。

## 暫存資源與非原子失敗邊界

每組 swap 使用 stack 的 24-byte scope：`173B6F0` 保存 arena block／offset，`173B8D0` 以 alignment=4 取得暫存，copy 完後保留原兩次 `173BC20`，回復同一 snapshot。

- 移入依序取得 38h、20h 暫存。
- 移出依序取得 70h、38h、20h 暫存。
- 相同 boundary 的快速路徑不呼叫這些 helpers。
- 第二次 release 的 scope 仍存在；不把它改為 null 或刪除第二次呼叫。

原 body 在第一個配置前已交換 pointer，移入還清零 primary。沒有 null-result／异常 rollback 路徑；候選保留這個順序。成功執行依賴 helpers 正常返回且無重入／交錯。它尚未提供配置失敗原子性或外部 allocator 恢復。

## 建置與驗證

以下只產生 JSON bytes artifact，輸出路徑必須不存在：

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 `
  eight_player_candidate_20260927/Native/roster_classify.py `
  --evidence five_player_feasibility_20260927/roster_classify_native_evidence.json `
  --remove-evidence five_player_feasibility_20260927/roster_remove_native_evidence.json `
  --insert-evidence five_player_feasibility_20260927/roster_insert_native_evidence.json `
  --move-evidence five_player_feasibility_20260927/roster_move_native_evidence.json `
  --producer-evidence five_player_feasibility_20260927/roster_property_producer_native_evidence.json `
  --receiver-evidence five_player_feasibility_20260927/roster_property_receive_evidence.json `
  --addresses eight_player_candidate_20260927/verification/native_roster_classify_addresses_synthetic.json `
  --output eight_player_candidate_20260927/verification/native_roster_classify_local.json
```

[7 組測試](verification/native_roster_classify_tests.json)通過 **853 次 x64 模擬執行**，包括 783 次候選／串接與 70 次原四格基準。660 次涵蓋全部合法八格 P/D/T/ordinal 組合；原四格另有 70 組 candidate/original 直接配對，核全四組 bytes、map 與 RAX。測試原始碼見 [test_native_roster_classify.py](tests/test_native_roster_classify.py)。

另驗九種 guard、P=0 移出／P=D 移入、滿／非滿 map missing ID、ASLR／hash collision、ABI、rel32 端點、十一函式交疊拒絕。連續 `enter 67 → enter 59 → leave 67 → leave 11 → receiver 67` 確認 ID 67 由 ordinal 7 移到 3 後，接收端真讀 map 並只寫 property[3]，wire network index 仍為 7。

暫存 helpers 使用明示契約 stub；驗 create→allocate→release→release、精確大小／alignment、24-byte scope、兩次 snapshot restore、暫存生存期、shadow space 與 volatile GPR/XMM 破壞。這不代表真實 allocator、重入、失敗恢復或外層通知已執行。

[獨立 source 審查](verification/native_roster_classify_review.zh-TW.md)核 429 條原指令及全部 88 個陣列位點；[獨立測試 oracle 審查](verification/native_roster_classify_test_review.zh-TW.md)核 byte 預期、原四格配對、guard／temporaries 及換位後接收。兩者均未發現此局部範圍剩餘阻擋缺陷。

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 eight_player_candidate_20260927/tests/test_native_roster_classify.py
```

依賴沿用本工作區 `.native-test-deps` 的 Unicorn 2.1.4／Capstone 5.0.7；不執行 host native bytes 或遊戲程序。這輪只重跑新增分類套件，既有十個來源與九套結果保持指紋。總共十套／115 組／3,870 次 x64 執行，其中兩次為先前移除套件的預期原程式反例，總數不是候選成功數。

## 尚缺的整合與下一步

尚無 sidecar 配置／移入／發布／重建／清理、reject handler、Windows unwind、hook、同步或遊戲執行。完整整理 `60CC70` 的 pending 所有權問題仍未解除；分類候選不能修復該缺口。實際 caller 對分類方向、primary 有效性與暫存成功的前提也尚未形成完整生命週期保證。

小型 `606AD0..606B75` ID→network-index getter 已納入 [0.10 候選](NATIVE_ROSTER_GETTER.zh-TW.md)，接到共同 B 並驗證分類／移除後的讀值。下一個有限切點為 `605950..605F2F` 的移除前處理與關聯 ID 讀取。其餘大型 reader、平台加入與第 5–8 名角色建立維持[工作清單](../five_player_feasibility_20260927/IMPLEMENTATION_WORKLIST.zh-TW.md)中的缺口；八人任務驗收仍未開始。
