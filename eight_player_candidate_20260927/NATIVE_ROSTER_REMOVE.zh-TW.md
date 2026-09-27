# 八格名冊移除候選

## 成品需求與狀態

[roster_remove.py](Native/roster_remove.py) 對應八人目標的離隊、移除後重新加入，以及其餘玩家 ID／記錄不被取代的要求。它保留兩個原生移除 ABI，加入刪除前的存在性檢查，並補上 dense 移除後遺漏的 pending 尾端搬移。

這是離線 x64 bytes 產生器。完整 caller、外部所有權、初始化／發布／清理、原生 hook、Windows unwind 與多人任務尚未完成，不能安裝或單獨啟用。下述八筆指合成名冊，沒有八個遊戲帳號參與。

## 來源與兩個原流程問題

固定 build `25480438`、Windows x64，沿用 manifest 的 EXE／game.dll 指紋。完整[原生證據](../five_player_feasibility_20260927/roster_remove_native_evidence.json)、[原指令分析](../five_player_feasibility_20260927/roster_remove_native_findings.zh-TW.md)及[獨立前提審查](../five_player_feasibility_20260927/roster_remove_native_prerequisites.zh-TW.md)保存兩個完整移除 body 與真實 deletion helper。

| 種類 | 原 body | 輸入及返回 | 候選大小 |
|---|---|---|---:|
| `legacy` | `60CEA0..60CF4C`，172 bytes／43 指令 | RDX=entity record；返回原 record `+10h` DWORD | 717 bytes |
| `registered` | `540A40..540AE0`，160 bytes／40 指令 | RCX=entity record；保留原返回 RAX 效果 | 705 bytes |
| map deletion | `172F8A0..172F9A3`，259 bytes／78 指令 | RCX=map descriptor、EDX=ID；命中回舊 ordinal | 使用原 helper |

原 deletion helper 未命中也回 0，與合法 ordinal 0 無法區別。原移除入口沒有先處理這個情況，會繼續減 counts／搬移。因此候選在刪除前先查 ID。

原 dense 分支在 `D<T` 時只從 dense 尾端補洞，同時減 T／D，沒有把原 tracked 尾端移入新 pending 範圍。例如 `[A,B]`、`T=2,D=1,P=0` 刪除 A，原 B 仍在超出新 T 的 slot 1。此反例是固定指令在明示合成狀態的結果，沒有證明真實遊戲會進入該狀態。

## 完整分段移除

定義 `T=[S+80h]`、`D=[S+84h]`、`P=[S+88h]`、目標 ordinal=n。前置有效狀態為 `0≤P≤D≤T≤8`，每筆 tracked 記錄有唯一有效 ID／map 對應，dense 範圍內 `n<P` 與 entity record `+14h bit0=1` 一致。

| 被刪目標 | 保留的原流程 | 新增的補位 |
|---|---|---|
| pending：`n≥D` | T--；若 n 不是舊 tracked 尾槽，將尾槽搬至 n；P／D 保留 | 無 |
| dense 非 prefix：`P≤n<D` | T--、D--；依原條件從舊 dense 尾槽補洞 | 若 `Dnew<Tnew`，將 slot `Tnew` 搬至 `Dnew` |
| prefix：`n<P` | P--；依原條件先搬 prefix 尾槽，再 T--／D--、搬 dense 尾槽 | 同上，補回 pending 尾端 |

**額外 pending 搬移是新增候選語義。** 原兩個函式沒有這一步。它同時涵蓋 `Dnew=0`、`Tnew>0`；沒有以要求 D==T 排除整個混合分段。當 D==T 時不執行額外搬移，原資料／map 行為可保留。

每次搬移使用既有完整四陣列 mover，pointer、70h primary、38h auxiliary、20h property 一起移動，並更新該 survivor 的 ID→ordinal。已存在的 prefix／dense 搬移只接觸原 `[0,D)`，所以 D<T 時舊 tracked 尾槽尚未被覆寫；將它放到新 pending 起點可保留所有 survivors。這是明示所有權與同步前提下的局部演算法，沒有閉合外部 slot aliases 或引擎資源生命週期。

物理槽位在新 T 之外保留舊 bytes，符合原 copy 型移除方式；它們不能因此被當成仍 active，也不能據此宣稱外部資源已釋放。`S+7Ch` 高水位保留原行為。

## 刪除前檢查與拒絕 ABI

前置檢查先保存 RCX／RDX／R8／R9 與 RBX／RSI／RDI，然後核對：

1. global `game+3326468` 指向指定 S。
2. `1≤T≤8` 及 `P≤D≤T`。
3. map capacity 等於此固定 roster profile 的八個 buckets。
4. ID 不等於 empty marker；按原 DWORD 乘法 hash，以最多八次探查找到 ID。
5. bucket ordinal 小於 T；共同八格 pointer 陣列該筆 record 的 ID 相符。
6. 若目標屬 dense，entity bit 與 prefix membership 一致。

讀查只用來拒絕上述不一致輸入，不能取代整個 map 的有效性前提。其他 survivor、唯一 keys、完整 probe chain、所有 dense flags 與同步仍須由整合層建立。Guard 後原函式會重新讀 global／map／counts；check/use 之間也必須處於同一執行保護。

拒絕入口由整合者提供。抵達時 RSP 回到 entry RSP，四個參數與所有非揮發 GPR／XMM 已保留，R10D 為原因 1–8；RAX／R11／flags 可改變。**會留下 56 bytes 的 scratch stack 寫入**，但沒有 roster、sidecar、map 或 entity 寫入。無效實體／map 指標的可讀性不是此機器碼可自行證明的條件。

原因碼依序為 binding、T 為零或超八、有序 counts、map capacity、missing／sentinel ID、ordinal 越界、prefix bit 不一致、pointer ID 不一致。它不提供恢復或假成功返回。

## 改接與 stack 細節

- 保留完整原指令，將短分支擴成 near 分支並重算目標，重定位 global RIP 讀取及 helper call／tail-jump。
- 唯一直接 pointer array load 改用共同 sidecar；原 map／counts 仍在 S。
- 原 dense completion test 導向新增 completion block；pending 分支的 `cmp(n,Tnew)` flags 與跳轉保留，沒有誤套 dense 的零值測試。
- Registered 原末端的 tail-jump 在 dense 分支改走有原 frame 的 mover call，使後續 repair 能執行；pending 分支仍保留原 tail-jump。
- 額外 repair 用 push RAX、`sub rsp,28h`、call、恢復 stack／RAX，提供 shadow space 與正確的 call alignment。Legacy 最後照原碼返回 entity `+10h`。這些 stack 操作尚未有已註冊 Windows unwind 描述。

## 共同建置與重現

新建置器沿用七函式插入 bundle，再加入兩個移除入口，共九個函式綁定同一個 S 與 `680h` 八格儲存。有限已知區域交疊檢查涵蓋兩個新 code／reject／原 body 及 deletion helper。[合成地址設定](verification/native_roster_remove_addresses_synthetic.json)與[九函式 bytes 範例](verification/native_roster_remove_bundle_synthetic.json)都不表示記憶體已配置。

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 `
  'E:\File\Codes\0\26.10.1\HD2\eight_player_candidate_20260927\Native\roster_remove.py' `
  --evidence 'E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\roster_remove_native_evidence.json' `
  --insert-evidence 'E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\roster_insert_native_evidence.json' `
  --move-evidence 'E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\roster_move_native_evidence.json' `
  --producer-evidence 'E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\roster_property_producer_native_evidence.json' `
  --receiver-evidence 'E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\roster_property_receive_evidence.json' `
  --addresses 'E:\File\Codes\0\26.10.1\HD2\eight_player_candidate_20260927\verification\native_roster_remove_addresses_synthetic.json' `
  --output 'E:\File\Codes\0\26.10.1\HD2\eight_player_candidate_20260927\verification\native_roster_remove_bundle_local_recheck.json'
```

Output 必須尚不存在。產生器只用 Python 標準函式庫與既有本地產生器；Unicorn／Capstone 只用於離線測試。版本指紋必須由未來整合層對真實映像核對，manifest 本身不執行 live 驗證。

## 驗證狀態

[測試程式](tests/test_native_roster_remove.py)已完成 9 組測試，0 failures／errors；[保存結果](verification/native_roster_remove_tests.json)含 2,293 次 x64 模擬執行：

| 分類 | 次數 | 證明範圍 |
|---|---:|---|
| 候選與串接 | 2,141 | 包含全部八格分段與目標位置、拒絕、ASLR、hash、邊界與連續操作 |
| 原四格基準 | 150 | 原四格布局，限定原流程能保留記錄的分段；registered 另有 75 組直接 RAX 配對 |
| 原程式預期反例 | 2 | 重現兩個 ABI 在 `T=2,D=1,P=0` 刪 dense 時失去 pending 的原結果；不列為候選成功 |

其中全部有效 `1≤T≤8`、`0≤P≤D≤T` 與每個目標 ordinal，兩種 ABI 共 1,980 次。獨立分區模型核全部 survivor ID、四組完整記錄、P／D／T、map 雙射與碰撞鏈可查找性，並比對其餘非 stack bytes；使用保存的真正 deletion helper 及 mover，沒有替換 helper。Map 的空 bucket 內殘留 value 不做逐 bit 正確性宣稱，活躍 key／value 與 probe 語義有另外檢查。

連續操作在同一名冊執行追加八筆、移除三筆、重新追加三筆、再接收屬性。最後選擇真正從 ordinal 7 移到 2 的 ID 67，確認讀取 map 並只寫入 property slot 2；incoming network index 仍為 7，沒有把 ordinal 與 network index 混同。Wire 是合成 bytes，沒有真實 serializer／網路傳輸。

[獨立 source 審查](verification/native_roster_remove_review.zh-TW.md)核前置檢查、原指令改接、dense／pending 分支、RAX 與 stack alignment，未發現局部缺陷。[獨立 oracle 審查](verification/native_roster_remove_test_review.zh-TW.md)提出的非零 ordinal 接收與 registered RAX 配對不足均已補強，最後套件重跑通過。

原有八套結果加上本套為 108 組、3,017 次模擬執行，其中包含上述兩次原程式預期反例；不可將總執行數全部稱為候選成功次數。既有九個 source 與八套保存結果沒有修改或重跑。

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 `
  'E:\File\Codes\0\26.10.1\HD2\eight_player_candidate_20260927\tests\test_native_roster_remove.py'
```

命令會更新本套 `verification/native_roster_remove_tests.json`，不操作遊戲。

## 仍需完成

原 `60CC70` 整理與 append 派送缺口保留；此移除補位沒有修復另一條整理路徑。分類、其餘讀者、全部 caller、四陣列配置／遷移／發布／清理、外部資源與同步、reject handler／unwind／hook，以及第五至八人任務全流程仍未完成。
