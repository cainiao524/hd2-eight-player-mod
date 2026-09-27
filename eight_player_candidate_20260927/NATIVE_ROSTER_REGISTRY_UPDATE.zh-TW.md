# Registry 更新與關聯 ID reader：離線八格原生候選

## 目的與固定來源

[原生 builder](Native/roster_registry_update.py)針對固定 Windows x64／Steam build `25480438`，複製完整 `B54E00` registry 更新函式及它在 tag `73h` 直接呼叫、會讀 roster 陣列的 `606520`。兩份候選共用既有 S 名冊、B 八格 sidecar。tag `69h` 的 property 搜尋、pointer 讀取、aux 狀態與 property flag 更新，以及 tag `73h` reader 的 property／pointer 讀取，均改接 B。其他 tag 的原分支、呼叫、RIP 參照與原順序保留。

來源只取自已保存的 build `25480438` capture：[完整逐指令 evidence](../five_player_feasibility_20260927/roster_registry_update_native_evidence.json)及相同 bytes 的[recheck](../five_player_feasibility_20260927/roster_registry_update_native_recheck.json)，兩者 SHA-256 均為 `7a8f289ea8ddf85d1b2010a39d9cedc4599e9846db8936b9e215cbd4a96740e1`。[有界 replay](../five_player_feasibility_20260927/roster_registry_update_native_replay.py)、[資料流 findings](../five_player_feasibility_20260927/roster_registry_update_native_findings.zh-TW.md)和[獨立前提](../five_player_feasibility_20260927/roster_registry_update_native_prerequisites.zh-TW.md)固定指令、CFG、unwind fragments、下標與 helper 邊界。原 body 分別為 `B54E00..B55169` 873 bytes／203 指令、`606520..60662F` 271 bytes／72 指令。另固定 `FD9BA0..FD9C7C` 220 bytes／59 指令，供真 helper 測試，**不產生它的替代碼**。

這是產生 bytes 的離線候選；尚無遊戲載入、可安裝 hook、拒絕 handler、Windows unwind 註冊或多人驗證。

## 原流程與八格改接

`B54E00` 入口 ECX 是輸入 ID。R13 從 global `3326E68` 取得 registry，按 entry tag `115h`、`73h`、`69h`、`2Eh` 走各自分支。tag `69h` 在 `B55003` 取 registry entry 的 roster `R14=S_registry`，以 `D=[S_registry+84h]` 遍歷 property。該分支後段 `B5505F` 又從 global `3326468` 載入 `R11=S_global`，用它查 map 並存取 aux；兩個來源在原 body 中沒有相等斷言。tag `73h` 則直接從 global `3326468` 取 S，傳給 `606520`。

共用 sidecar B 的布局仍為 pointer `B+0`、primary `B+40h`、aux `B+3C0h`、property `B+580h`，四組 stride 分別為 `8/70h/38h/20h`。原 count、map 與 registry 保留在 S／registry。

| 原函式與位點 | 原存取 | 候選目的 |
| --- | --- | --- |
| `B5501C` 產生 RDI，`B55030/B5504A` 間接讀並前進 | `S_registry+3A8h+ESI*20h` property 首 DWORD | RDI 從 `B+580h` 開始；保留每步 `20h` |
| `B55057`、`B550E9` | `S_registry+E8h+ESI*8` pointer | `B+ESI*8` |
| `B550CD`、`B550D8` | `S_global+2E0h+n*38h` aux 的 `+18h` DWORD | `B+3D8h+n*38h`；保留「若不等於 2 才寫 1」 |
| `B550FB` | `S_registry+3ACh+ESI*20h` property flag DWORD | `B+584h+ESI*20h`，保留按 entity bit 0 條件清 bit 0 |
| `606559` 產生 R14，`606560/6065EA` 間接讀並前進 | explicit `S+3A8h+RBX*20h` property 首 DWORD | R14 從 `B+580h` 開始 |
| `606622` | explicit `S+E8h+RBX*8` pointer | `B+RBX*8` |

root 有 **6 個直接 patch**，helper 有 **2 個直接 patch**；間接 `[RDI]`／`[R14]` 讀與 stride 指令保留。root 輸出為 **1,683 bytes**，含 53 個重定位項（原 40 個局部分支、7 個 RIP reference、6 個直接 call）；helper 為 **416 bytes**，含 14 項（11 個局部分支、3 個 RIP reference）。原 root 的兩個間接 call 保留；直接 `B54F23` 只改呼此共同 B 的 `606520` clone，其他外部直接 call 保留原目的位址。保留 R14／R11 的原 S 角色、tag `73h` 的獨立物件 RDI、tag `115h` 的獨立物件 RSI，避免把非 roster 資料也改成 B。

`FD9BA0` 的 tag `69h` 呼叫仍用原目的位址。它接 property 首 DWORD 的關聯 ID，從另一個 context reverse-map 寫 caller out-DWORD，不讀 roster；不可用 `606520` 或 network-index getter 代替。兩個原 helper 對關聯 ID `7FFFh` 的行為亦不同：`FD9BA0` 寫 context 預設值，`606520` 略過該 property record。tag `73h` 的 opaque stack `+20h..2Fh`、其他資源操作及間接 call 的原 bytes 保留，不能把未知輸出宣稱為已初始化的零值。

## Guard 與拒絕狀態

候選只在使用 roster 的兩個分支加檢查，不把 roster guard 無條件加到其他 tags：

1. tag `69h` 於 `B5500B` 前，已取得 registry S、尚未讀其 D／property 時，核 `S_registry == 指定 S == global S`，並核 unsigned `P≤D≤T≤8`；`D=0` 仍可按原流程略過。
2. tag `73h` 於 `B54F23` 呼叫前，核該次傳入的 global S 與指定 S、`P≤D≤T≤8`；`606520` clone 的獨立入口再核其 RCX=S 與 counts，不自行重新讀 global S。兩層檢查之間的穩定性仍由整合者保證。
3. tag `69h` 命中 property 後，在首次解參 entity 前拒絕 null pointer；進入 map 前要求容量 8、entity ID 不等 map empty key。原 map 結果到 aux 之前，拒絕 `n≥8`、`n≥T` 或 `n≠ESI`。

這些額外拒絕是候選的新安全政策：原碼容許 missing／`FFFFFFFFh` map ordinal 進入 aux 地址，也沒有 `S_registry == S_global` 或 `n==ESI` 的斷言。aux 的 n 來自 map，property 的 ESI 來自遍歷；不能在改接時偷換兩者。候選沒有加入「entity flag 等於 prefix 分段」的原碼未證限制。map 的 backing、key domain、雙射與 target／sidecar 指標生命週期仍是外部契約。

兩個函式各需整合者提供**不同 frame**的 reject continuation。root 的拒絕還原原入口 RSP 與 nonvolatile，ECX 恢復輸入 ID；helper 的入口拒絕保留 RCX/RDX/R8，不寫輸出。R10D 攜 1–9 中的適用原因碼；其他 volatile／flags 不承諾保持。root 在某個較後 registry entry 拒絕時，**較早 entries 可能已呼叫外部函式或修改其物件**；這不是可回滾的整體交易。拒絕入口如何終止或恢復 dispatch 仍未實作，不能假設直接返回即可安全繼續。

tag `69h` 的 `FD9BA0` 與 `606520` 仍使用原 context map 演算法；零容量、完整 miss 或 empty-key 假命中可能使它們讀 null／錯資料。候選的 roster guard 不會驗 context map、資源分配或真實回呼重入。tag `115h`、`73h` 的外部 callback 與 tag `2Eh` 呼叫也保留原效果及同步前提。

## 建置與目前驗證界限

[合成地址](verification/native_roster_registry_update_addresses_synthetic.json)與[共同 bundle](verification/native_roster_registry_update_bundle_synthetic.json)只示範離線地址配置。`build_bundle` 共產 **十五個 roster 函式**，攜帶上一版**不變的 player-count patch 計畫**；它對 **59 個有限已知區域**檢查重疊，包括兩個新 code、兩個不同 reject address 與相應原函式。這不等於全程式地址／別名覆蓋。所有 source bytes、evidence SHA、對齊及 rel32 範圍都由 builder 檢查；產物含 `entry_or_callsite_patch: null`，沒有實際把程式入口換到新 code。

在 workspace 根目錄執行；輸出路徑必須尚不存在：

```powershell
& 'C:\Program Files\Python312\python.exe' -B eight_player_candidate_20260927/Native/roster_registry_update.py `
  --evidence five_player_feasibility_20260927/roster_registry_update_native_evidence.json `
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
  --addresses eight_player_candidate_20260927/verification/native_roster_registry_update_addresses_synthetic.json `
  --output NEW-registry-update-bundle.json
```

[本輪測試報告](verification/native_roster_registry_update_tests.json)記錄 **8 方法、87 次頂層 x64 執行，全部通過**：12 次原碼基線、75 次候選；候選細分 root return 32／reject 20、helper return 17／reject 6。內層真 `FD9BA0` 入口 114 次、原／候選 nested `606520` 入口 1／7 次另列，**不加進 87**。[獨立 oracle 審查](verification/native_roster_registry_update_test_review.zh-TW.md)核了測試位點、完整非 stack 記憶體及 ABI oracle、報告計數與替身界限；[獨立 source 前提審查](../five_player_feasibility_20260927/roster_registry_update_native_prerequisites.zh-TW.md)列原函式與必要 helper 契約。tag `2Eh`、`115h`、tag `73h` 資源 callback 與兩個 indirect call 在執行測試中仍為明示契約替身；只可驗所設參數、順序和副作用，不能證明真實資源可用。舊候選在這輪僅共同 build，沒有重跑舊套件。

現階段未配置／初始化／搬移或發布 B、未覆蓋所有 roster reader／writer、未提供 hook、拒絕 handler、unwind、撤回流程及五至八帳號同場任務驗收。此候選仍不可安裝。
