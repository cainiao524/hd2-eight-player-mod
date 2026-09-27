# `6054F0` 狀態更新：離線八格原生候選

## 用途與固定來源

[builder](Native/roster_arrival.py)的 `arrival` 只是一個工作檔名。完整原函式 `6054F0..605947` 接 entity 與 caller state object，查 roster map 後更新 pointer／primary／aux／property 的部分欄位、讀 network index 決定 palette，並發出數次玩家數通知；它**沒有 append、count 遞增或完整加入 caller 證明**。本候選把此函式內四組 roster 記錄改接共同八格 sidecar B，保留原 S 的 map/header/count 與原指令順序。它不建立或發布 B。

來源只取自固定 Windows x64 Steam build `25480438` 的既存 capture。[完整原指令 evidence](../five_player_feasibility_20260927/roster_arrival_native_evidence.json)和[獨立 recheck](../five_player_feasibility_20260927/roster_arrival_native_recheck.json)逐 byte 相同，SHA-256 均為 `c3073ba7658599bc662d980397f21bf7a003f56a2b821cdcf4c2341fe05a2e64`；[有界 replay](../five_player_feasibility_20260927/roster_arrival_native_replay.py)及[資料流 findings](../five_player_feasibility_20260927/roster_arrival_native_findings.zh-TW.md)固定完整 body 1111 bytes／241 條指令、單一 unwind fragment `2424950`、41 個 local branch、23 個 RIP 參照、4 個 direct call、4 個 indirect call 與全部 19 個陣列位點。[獨立前提審查](../five_player_feasibility_20260927/roster_arrival_native_prerequisites.zh-TW.md)記載入口 ABI、旗標生命期、callee 邊界與 count 契約。原 body SHA-256 為 `6ad21683150fa35285c490fb75b00d8f0af68ab36dad70cbced0bccfc745288a`。

另固定不變的 `FD9AF0..FD9B9E` 174-byte context 轉換 leaf，供有效命中路徑的原指令測試，**不發射其替代碼**。四段 readonly 來源包含四列 64-byte palette、1.0f、255.0f 及 `player_count\0`；沒有創造新的第五至第八列資源。

## 完整四陣列改接

入口 RDX=entity pointer、R8=caller state object。原 `605530` 從 global `3326468` 讀 RDI=S，於 S map 查 `[entity+8]` ID 取得 ordinal `n`。所有原始 S header/map/count 與 S+8 仍指向 S；新陣列布局與其他候選相同：pointer `B+0`／stride8、primary `B+40h`／stride70h、aux `B+3C0h`／stride38h、property `B+580h`／stride20h。`n` 與 property+Ch 的 network index 是兩個不同數值。

| 四組 | 原函式位點（共同前綴 `605`） | 候選八格目的 |
| --- | --- | --- |
| pointer，2 個 | `5BB` 讀 entity pointer、`626` 建 dense loop base | `B+n×8`、`B` |
| primary，4 個 | `665/684/691` 寫 `+38h` 的互斥狀態 5／8／1，`6A6` 清 `+60h` QWORD | `B+78h+n×70h`、`B+A0h+n×70h` |
| aux，9 個 | `6B8/6C8/6D6/6F3/700/709` 寫 status／sentinel、`758/801` 存及重讀關聯物件 pointer、`83C` 條件覆寫 status | 同一 `B+3C0h+n×38h` 記錄的原相對欄位與原 byte／DWORD／QWORD 寬度 |
| property，4 個 | `5CD` 設 bit11、`61F` 建 dense loop base、`6E6` 讀 flag byte、`760` 讀 network index DWORD | `B+584h+n×20h` 及 `B+58Ch+n×20h` |

兩個 LEA (`60561F/626`) 會供後面的間接讀與 stride 前進，故同樣是必要改接點。完整 clone 保留原 RDI=S；對直接 operand 只在該指令使用 B 的局部基址，沒有永久 bias RDI。原 `6056F0` 的 ZF 必須穿過 aux stores 留給 `605707 JNE`；`60579D` mode 比較的 ZF 穿過 palette 浮點計算留給 `6057CA JNE`。原 EAX ordinal 也跨可選 primary 支線活到 `6056B2`。builder 在改接片段保留這些原控制流與 live 值，完整 emitted bytes 仍需以有界 x64 測試檢查。

`605760` 讀的是完整 network-index DWORD。原碼只有 index unsigned `<4` 才從四列 `213F4E0` palette 取值；`4–7` 沿原 fallback 使用三個 1.0f，再乘 255.0f，形成白色 `(255,255,255)`。本候選維持這條有界路徑；沒有把 palette 比較常數改 8，也沒有聲稱不同玩家已有獨立顏色或具名 HUD 資源。

## Preflight、拒絕與未解副作用

原 map miss 會留下零延伸的 `FFFFFFFFh` ordinal，後續仍可落到巨大 unsigned array offset。本候選在完整原 prologue 和任何原 payload／外部呼叫**之前**加入口 preflight。它保留 RCX/RDX/R8/R9 與所用 nonvolatile 暫存，然後依序檢：

1. global `3326468` 的 S 與共同指定 S 相同；target entity 與 R8 caller state object 非 null。
2. `0<T≤8`、`P≤D≤T`，S map 容量恰為 8。
3. entity ID 既非 map empty key，亦非 global `3483C20` invalid sentinel；有限八 bucket probe 必須找到該 ID。
4. map ordinal `<T`，且 `B.pointer[ordinal]` 恰指 target entity。

失敗只跳到**由整合者提供**的 `reject_address`，R10D 為 1–10 的原因碼；原入口 RSP、RCX/RDX/R8/R9 和 nonvolatile GPR／XMM 可保留，RAX/R11/flags 不承諾保持。preflight 為暫存保存而寫原入口 RSP 以下 56 bytes；拒絕前沒有非 stack 寫或外部 call。成功恢復暫存後才執行完整原 body。候選不提供 reject handler、入口 hook、Windows unwind 註冊或任何自動退回方式；整合者須使拒絕路徑安全終止本次 dispatch。

Preflight 只核當時的 member 狀態，不提供目標記憶體可讀性、map／B／entity ownership 或回呼同步。R8 首 byte 非零時，原 body 另解參 `[R8+48h]` 指向的物件與其 `+624h`；原 context map、mode4 manager record、通知資源及各 indirect callback 也需外部有效契約。原 body 在完成前會修改 B 及其他 global／物件；後續外部 call 失敗或重入時，候選沒有 rollback。

## 呼叫、玩家數與輸出

完整原 body 的四個 direct calls 是 `FD9AF0`、`94C9C0`、`60C2A0`、security-cookie helper `2088770`；四個 indirect calls 是兩個關聯介面、條件式 palette endpoint、`player_count` 通知。原 cookie/frame/epilogue 都保留。`FD9AF0` 使用另一個 context forward map，無 roster 陣列可改；`94C9C0` 和 `60C2A0` 沿既有 count 證據與共同 player-count patch 計畫，其他 callback、資源和 cookie helper 的真實行為並未由本 builder 證明。

本函式沒有修改 D。`94C9C0` 條件呼叫從重新載入的 global S 取當時 D；`60C2A0` 及後續 `player_count` 通知則從先前持有的 RDI=S 讀 D。它們位於數個 callback 前後，只有在外部維持 S 身分及 roster 狀態穩定時才可視為同一狀態。這裡不採用 departure 的預期移除後 count 公式，也不假定 pending 的額外計數。

[合成地址](verification/native_roster_arrival_addresses_synthetic.json)與[共同 bundle](verification/native_roster_arrival_bundle_synthetic.json)只展示離線配置。[候選原始碼](Native/roster_arrival.py) SHA-256 `2744e367accb26d022807984b8a573d95cc6e9ec15c011c5b403ee187e030771`，產生完整 **1917 bytes** root code：19 個陣列 patch、41 個 local branch relocation、27 個外部 relocation（23 RIP／4 direct call），保留 4 個 indirect call。`build_bundle` 共 **16 個 roster 函式**，帶入**不變的 player-count 計畫**，並核 **62 個有限已知區域**不重疊，包括新 code、reject 與原 `6054F0` body。兩個 synthetic JSON SHA-256 分別為 `e2ca74722a5d6eed3d2ede6eebd1b7130a2a931e9316a92333f170559fc552a6`、`a9268253612ad82778491308acec824e83a27afb1f9d19313994657f3dc248e0`。`entry_or_callsite_patch` 為 null：產物沒有安裝或啟用的地址轉跳。

在 workspace 根目錄重建 bundle；輸出路徑須尚不存在：

```powershell
& 'C:\Program Files\Python312\python.exe' -B eight_player_candidate_20260927/Native/roster_arrival.py `
  --evidence five_player_feasibility_20260927/roster_arrival_native_evidence.json `
  --registry-evidence five_player_feasibility_20260927/roster_registry_update_native_evidence.json `
  --departure-evidence five_player_feasibility_20260927/roster_departure_native_evidence.json `
  --getter-evidence five_player_feasibility_20260927/roster_getter_native_evidence.json `
  --classify-evidence five_player_feasibility_20260927/roster_classify_native_evidence.json `
  --remove-evidence five_player_feasibility_20260927/roster_remove_native_evidence.json `
  --insert-evidence five_player_feasibility_20260927/roster_insert_native_evidence.json `
  --move-evidence five_player_feasibility_20260927/roster_move_native_evidence.json `
  --producer-evidence five_player_feasibility_20260927/roster_property_producer_native_evidence.json `
  --receiver-evidence five_player_feasibility_20260927/roster_property_receive_evidence.json `
  --player-count-evidence five_player_feasibility_20260927/roster_player_count_native_evidence.json `
  --context-evidence five_player_feasibility_20260927/roster_departure_callee_evidence.json `
  --addresses eight_player_candidate_20260927/verification/native_roster_arrival_addresses_synthetic.json `
  --output NEW-roster-state-update-bundle.json
```

本輪執行測試及獨立 oracle 審查將在報告凍結後連結。即使局部機器碼測試通過，也仍缺 B 的配置／初始化／遷移／發布／清理、所有 roster reader／writer、caller 與 callback 生命週期、真實資產、hook／unwind／reject handler、遊戲執行及五至八帳號同場任務驗收。此候選目前不可安裝。
