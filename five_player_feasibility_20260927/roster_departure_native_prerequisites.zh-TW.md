# 605950 移除前清理：原生八格改接的有限前提

## 1. 成品需求、實作決策與停止條件

本輪需要在分類、搬移與移除已改接外部八格陣列後，讓原 `605950` 移除前階段讀到同一筆 entity 的 pointer、primary 與 property。需要保留原資源解除、關聯 entity 處理及通知次序，不能把這一階段當成單純呼叫 roster remove 的 wrapper。

**有限結論：可以界定六個直接陣列讀取及一個額外 network reader 的修改點；目前不能據此宣稱八格 departure 生命週期閉合。** 兩處 `D−1` 對 pending target 的語義未由 caller 證明；其中一個接收者 `94C9C0` 更明確把傳入玩家數限制在 `[1,4]`，供通知及其他計算使用。這是下一步實作決策所需的具體來源，不能藏在外部無副作用 stub 中。

本輪停止於完整 `605950`、必要 `606820`、既有 `FDC820` caller 及下表限定直接 helper。未追蹤任意 callee 樹、未掃描整份 capture、未操作任何遊戲程序。未修改候選 emitter、既有正式證據或總報告。

## 2. 固定來源與重現範圍

固定 capture 目錄：

```text
C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438
```

| 來源 | SHA-256 |
| --- | --- |
| capture-report.json | `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5` |
| captured-data.bin | `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d` |
| capture identity | `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8` |
| 既有 roster_property_apply_evidence_v3.json | `d0dd9c02db933c20801a366d9668131734a29106e46f8a8a0d0de43981a27d22` |
| 既有 roster_property_apply_605950_disasm.txt | `40f2f07a2aac63b55b4b333ac42dbe53e3d433d26343bd180d22a0e036cbcfe3` |
| 既有 roster_property_apply_fdc820_disasm.txt | `d0a54f80a8ec52bf95fb8053dc21e51d859114ac534faa1c5ad3b7dd2e64559c` |

本輪逐筆將 `605950` 的既有反組譯與 capture 比對；必要 helper 直接由固定 bytes 解碼。RVA 範圍均為左閉右開。`inspect_capture.Image` 先驗證上述 capture 指紋，再讀取已保存 unwind 及 code。PE header 指向的 exception directory 不在捕捉範圍，使用的是另外保存且有標記的 unwind table。

| 完整範圍 | bytes | SHA-256 | 本輪用途 |
| --- | ---: | --- | --- |
| `605950..605F2F` | 1503 | `4f0de56eb062df3180f58fcf4fd9a4e462eceba75a3077ac2bc22728500f5681` | 346 條指令、13 unwind fragments，全本文本及資料流 |
| `606820..6068E5` | 197 | `0ee6495101f1fbd8c4a95731144aa5dbd43289f107264c12c4d2d9aab9ffd2ce` | 51 條指令、3 fragments，network reader |
| `FDC820..FDCDFF` | 1503 | `8ef7ad9fbf59756023045f94c796bfb96a2f43876d8c64052c0d306a8b5c6094` | 既有 caller 的派發前條件與兩階段次序 |
| `B0B020..B0B1C4` | 420 | `5e4eb6a1ec43b034743f67d84cf8af24a83bcbf8c4851211e2074ccb6600d1d4` | 第一個 primary 註冊解除 |
| `B11C20..B11DC4` | 420 | `2cfbab65bc09dab531e0d6d40068a47e7e13a95f1f039ffff5795fb813768b25` | 第二個 primary 註冊解除 |
| `B0F820..B0F9C4` | 420 | `533fada65b0fe0477682f7fa97a9c346c0bc3d503065d6e4d211f793b3a4afaa` | 第三個 primary 註冊解除 |
| `60C2A0..60C33F` | 159 | `66ce04f430d2fc2d46c023d5d7cff18bb19cca43a0f43eaf72fa842b01f066d6` | count 數值及四種資源分支 |
| `FD9C80..FD9D33` | 179 | `0533fa336a0f696021412e722716c7de8ee2096439a98f7e8671a9ea44487eae` | property 首 DWORD 的關聯 entity 解析 |
| `FD9D40..FD9DF2` | 178 | `27627b0418666a4ce50917587d9dd779c3736a8af2272a3a3c955f94cb3701ed` | 關聯 entity ID 解析及 ECX 保留 |
| `FDC310..FDC40A` | 250 | `774652c9ef50dde18f79f969fc77f54a07f8b5fac561b9fead11eec1d9730b64` | 有界確認 queue append / event 分支 |
| `94C9C0..94D308` | 2376 | `7cc342fdc09d11b0bde285b179adcd4b5356df5df667be89bd7d5c6f76ca4ef2` | 只分析輸入計數 clamp、通知、傳遞；此完整 unwind 範圍含 `94D29C..94D308` jump tables，不把表資料計為可執行指令 |

`606820` fragments 是 `606820..606851 / unwind 2424BD4`、`606851..6068DB / 2424BDC`、`6068DB..6068E5 / 2424BFC`。`605950` fragments 為 `605950..605969`、`605969..60596D`、`60596D..605A63`、`605A63..605B7C`、`605B7C..605BD3`、`605BD3..605BF9`、`605BF9..605C50`、`605C50..605CCF`、`605CCF..605CE1`、`605CE1..605D18`、`605D18..605DE1`、`605DE1..605E4C`、`605E4C..605F2F`。逐 fragment 指紋及完整指令另由本輪 departure evidence 固定，不依動態程序資料。

可重現的有限讀取方法：把 workspace 的 `.native-test-deps` 及 `research_handoff_20260927/indirect` 放入 Python `sys.path`，設定 `sys.dont_write_bytecode=True`，建立 `Image(上述目錄)`；對表列範圍呼叫 `im.read(start,end-start)` 計算 SHA，使用 `im.instruction(RVA)` 驗證本文位點。不要呼叫其全 capture `scan()`。以 `im.read(0x224CF30,12)`、`im.read(0x2247550,35)` 可重核本文兩個計數字串。

## 3. ABI、frame 與原名單查找

- 輸入 `RDX=target entity`；`605975` 將它保存於 R14。原 RCX 只在 entry home slot 保存，不能當成函式的 roster 參數。
- `605962` 從 global `3326468` 載入 roster S 至 R13。後續 S 由 R13 跨回呼保存；`605E87` 另重新讀取一次 global S，故兩者相同需要生命週期前提。
- 設 entry RSP 為 E：push RBX/RDI/R13，再 `sub RSP,80h`，body RSP X=E−98h，call 時符合 16-byte 對齊。
- 原 RBP、RSI、R14 分別保存於 E+10h、E+18h、E−20h，即 body 的 X+A8h、X+B0h、X+78h。XMM6 在 X+60h；條件支線另保存 R15 於 X+70h、R12 於 X+B8h。
- 輸出 DWORD 使用 X+A0h（原 entry home 位置 E+8h）。X+20h..50h 用作 outgoing arguments，不能挪作長期 local。
- 結尾先恢復 frame，再於 `605F28` 間接尾跳 engine interface `+480h`。原 body 沒有本地 RET，也未在本地寫 P/D/T。

初始以 `[target+8]` 查 `S+D0/D8/DC/E0` map。原 miss 或 invalid ID 會得到 `EDI=FFFFFFFF`，但沒有在此 return。命中會先讀 pointer[n] 並可能呼叫 `13462C0` 的 `disconnected` 通知，然後才進入 `6059DB` 主段。

原 `605A5B` 無條件以 `n*20h` 讀 property 首 DWORD。故僅在該指令前限制 ordinal 仍不能防止更早的通知與 `606820` 非法讀取；如新增拒絕，應在第一次陣列讀取／外部回呼前乾式驗證 ID、map、ordinal 和已選 storage 身分。這是新候選行為，不能聲稱原 miss 安全。

## 4. 八格陣列改接的精確集合

| RVA | 原 operand / 來源 | 八格候選位置 |
| --- | --- | --- |
| `605A0D` | `[R13+RCX*8+E8]`，RCX=n | `B+n*8` |
| `605B96` | `[R13+RDI*8+E8]`，RDI=n | `B+n*8` |
| `605A26` | `[RDI+R13+108]`，RDI=n*70 | `B+40+n*70` 首 DWORD |
| `605A3A` | 同上 | 同上；第二 helper 前重新讀 |
| `605A4E` | 同上 | 同上；第三 helper 前重新讀 |
| `605A5B` | `[RSI+R13+3A8]`，RSI=n*20 | `B+580+n*20` 首 DWORD |

完整 body 無直接 aux 讀寫；上述 property 首 DWORD 與 network index `+Ch` 是不同欄位。三個 primary helper 的 RDX 必須仍是原 S，用作外部 registration tuple 的 owner 身分，不能因 storage 改接而改成 B。

另有 `6059EE call 606820`，原 ABI `RCX=explicit S, EDX=ID`。該 helper 兩處 `60683A / 6068CE` 使用相同 bytes：

```text
42 8B 84 11 B4 03 00 00     mov eax,[rcx+r10+3B4h]
```

其中 R10=S、RCX=ordinal*20h。global invalid ID、cap=0、普通 miss 都仍會走到使用 FFFFFFFF ordinal 的讀取；不能把它當已具備 missing return 的既有 getter。

在 **這一個 callsite** 改呼既有 `606AD0` 八格 getter 候選有條件成立：`6059F3` 馬上載入新 RCX、`6059FA` 只使用返回 EAX 當 EDX，因此沒有 explicit-S callee 其他 volatile 輸出的依賴。但需要整段期間 `global S == R13 == binding S`、map/sidecar 仍有效，且 entry 查找後沒有改變 ordinal 身分。新 getter 的 guard 與 missing 語義不同；這是明示的 callsite 替換，不能全域替換 `606820` 或宣稱兩函式所有輸入等價。

## 5. 原資源與通知次序

下列為原控制流的階段摘要，不將可選分支當成每次皆執行。

1. 查找成功、pointer[n] 的 bit 0 及 mode 允許時，`605BC9` 發 `disconnected`（RCX=該 entity、R8B=1、R9D=0），再回主段。
2. target ID 不等第二 sentinel 時，`6059EE` 讀 network index，再由 `6059FC call 139C360` 消費該 EAX。
3. pointer[n] bit 0 成立時，`605A2E / 605A42 / 605A56` 依序呼叫 `B0B020 / B11C20 / B0F820`。三次均重新讀 primary[n] 首 DWORD；不可只快取一次而假設前三個回呼不會影響資料。
4. `605A68 call FD9C80` 以 property[n] 首 DWORD 解析關聯 entity。後續行為依全域 mode、target bit、關聯 entity bit 與 handle 驗證分支。
5. 特定 mode=4 的分支包含 engine 間接 handle 驗證、`838680`，對另一 manager `3326D20` 查找及 `A747D0 / A74700 / A77800`；再可能有 `135A4A0 / BE21A0 / FD9D40 / 13BFB40 / 135AB10 / BE16F0`。這些不得被簡化為無副作用成功。
6. 關聯 entity 或 manager list 中符合 type/bit 條件的其他 entity，經 `605DC6 / 605E17 call FDC310`。list loop 在 call 後重新讀 manager global 與 count。
7. registry `3326E68` 的 tag=3E entry 且 mode=4 時，`605EDE call 94C9C0` 接收當時重新讀 global S 的 `D−1`。
8. `605EFA call 60C2A0` 接收 held R13 S 的 `D−1`。
9. `605F28` 尾跳 engine interface，字串 `player_count`（22473C8），EDX 為尾部再讀的 **未減一 D**。

在已核 body 中沒有直接 call `60CEA0` 或 `540A40`，也没有本地 map delete。這個事實不表示所有外部回呼都不會改變 roster。

### 有限必要 helper 契約

三個 primary registration helper 的完整 body 只把 S 與 24-byte tuple 的 owner pointer 比較，並把 ID 與 tuple+10h 比較，未以 S 解參四個 roster 陣列。但是它們確實移除 tuple，某 mode 下清空 pointer，另一 mode 下以尾 tuple 填洞並扣 count；list 變空時可能間接釋放 backing、清 descriptor、修改子系統 count，最後呼叫 `172F9B0`。其原資源副作用不可省略。

`FD9C80` 對明示的 `7FFF` key 有 null 路徑；不能推廣為所有 map miss 都安全返回 null，cap=0/full-scan miss 的部分路徑仍可能對零指標比較。`FD9D40` 的正常保存指令查找保持 ECX，原 `605D34` 返回後立即把 ECX 放入 R8D；用任意 clobber RCX 的 stub 不能當成該實際 helper 等价。

有限 `FDC310` body 可證兩類操作：向 manager 的 `+F3EF20` queue 寫 ordinal 並增加 `+F3EF18`，或進入 `BDE430` event 呼叫。未見直接同 S count 寫入；其 event 下游未展開，所以不能證明不重入、不間接移除、不更換 global S。

## 6. Caller 是否證明 target 只在 dense？

既有同 context 派發鏈為 `FDC820 → 540B20 → 605950`，其後另一表才選到 registered remove `540A40`：

| 位點 | 已證行為 |
| --- | --- |
| `FDC943 / FDC953` | 原 context `+F0DFB0`，依 descriptor component list 派發移除前階段 |
| `FDCC53 / FDCC63` | 同 context `+F0E9D0`，較後派發實際 roster remove |
| 更後段 | engine 刪除及 entity 欄位失效化 |

對 `FDC820` 的有限前提核對：entity 非 null、ID 不等另一 global sentinel；`FDC869 test R8B` 後 `FDC86C jne FDC8AD` 可跳過附加 type/bit 檢查。R8B=0 分支對 entity+10 的 7FFF 特例測 bit 0，其他 type 經外部 callback 要求 EAX>0。之後 `B4BAD0` 與 descriptor component list 查找，不含已證同 S ordinal 對 D 的比較。

因此 **本段不能證明只接 dense target，也不能證明 pending target 在真實遊戲必然可達**。未展開的 `B4BAD0` 或更外層 caller 可能有其他契約。本輪不得用新增 `n<D` guard 排除 pending 並稱已解決全生命週期。

## 7. 兩個 D−1 接收者與明確八人格限制

### 7.1 `94C9C0`：`num_players` 並非未限制的八格值

`605E95` 讀 D，`605EA2 dec EDX`，`605ECE` 存到 caller `[RSP+28h]`。進入 `94C9C0` 後 7 個 push 加 100h frame，使該参数位於 callee `[RSP+168h]`：

```text
94CA1D  8B AC 24 68 01 00 00   mov ebp,[rsp+168h]
94CA24  83 FD 01               cmp ebp,1
94CA27  73 07                  jae 94CA30
94CA29  BD 01 00 00 00         mov ebp,1
94CA30  B8 04 00 00 00         mov eax,4
94CA35  3B E8                  cmp ebp,eax
94CA37  0F 47 E8               cmova ebp,eax
```

此為 unsigned clamp `[1,4]`。`94CBDE` LEA 指向 `224CF30 = "num_players"`，`94CBE5 EDX=EBP`，`94CBEB` 呼叫 engine interface `+480h`。已限制的 EBP 亦在 `94CC60` 等多處存 outgoing `[RSP+38h]` 給 `94BE10`，不能只視為畫面文字。未追 `94BE10`，沒有證明把上限改 8 可安全覆蓋其資料表、分配及計算。

由此可得：caller 即使把 `D−1` 改為條件式剩餘 dense count，傳入 5..7 仍被轉為 4，傳入 0 轉為 1；原 D=0 的 unsigned `FFFFFFFF` 則也轉為 4。這些是固定指令可證的數值結果；不依賴實際 pending 可達性。

### 7.2 `60C2A0`：四種資源分支與數值 fallback

輸入 EDX 保存至 EDI。1、2、3、4 各選一個 hash，經 `12556E0` 與 engine `+1E8h`；其他輸入略過此 hash 分支。最後所有分支都走 `60C31F` 的 `2247550 = "Multiplayer_NumberOfActiveTeammates"`，`CVTSI2SS XMM1,RDI` 把零擴展 DWORD 轉為 float，尾跳 engine `+A0h`。

因此 5..7 存在數值通知路徑，但沒有對應四個以外的已證命名資源切換。D=0 先減一會將 4294967295 轉為 float，而非 clamp 0。字串支持「玩家／隊友數消費」的有限判定，不能單靠字串斷定 pending target 是否應執行此整段。

### 7.3 候選公式的界限

既有 remove 候選对有效 unique/map state 的 count 變化為：dense target 扣 D；pending target 不扣 D。依此提出 `remainingD = D − (n<D)`，在同一 state 快照下能與後續 remove 的算術一致。但以下尚未證明：

- `605950` 中原兩個消費者期待的是否正是該未來 remove 的 D，而非其他時序／活動範圍計數。
- 多個通知與 engine callback 期間 S、map、ordinal、P/D/T、target 身分及 storage 是否維持不變。
- 原末尾 `player_count` 傳當時 D 的行為是否應保持，及相對前兩個通知的契約。
- 如何處理 `94C9C0` 的 `[1,4]` 限制及其 `94BE10` 使用；只改 caller 沒有閉合。

候選若使用新 local 保存 prediction，frame `80h→90h` 並將原 RSP 相對 local/save operands `>=60h` 加 10h、outgoing `20h..50h` 保持原位，是可以另行驗證的機器碼方案；原 RAX=entry RSP 的保存位置不需改。但在 `6059DB` 計算時，原 disconnected callback 已可能執行，故單靠 entry guard 不能把此 prediction 當成 entry state 的可靠持續承諾。這裡只列必要實作審查點，未批准該公式為遊戲真實生命週期語義，也未實作或測試 frame 改寫。

## 8. 下一步及不越界的驗證要求

上述原四格有界仿真已完成為 [probe v2](roster_departure_native_probe_v2.py)及[結果](roster_departure_native_probe_results_v2.json)。三個 dense／pending／D=0 狀態均實際執行 605950、606820、FD9C80、540A40 及 map-delete；FD9C80 使用 7FFF 的真實 null 分支，取代早期 probe 的強制 null 替身。兩個通知的 D−1 與 pending 實際移除後 D 不同，D=0 時前者下溢。四個外部通知仍採不干擾契約，外層派送仍是合成的呼叫次序。這固定的是條件式參數 trace，不能把 stub 當成通知資源生命週期證明。

已檢視的三個 primary helper、FDC310、FD9C80、60C2A0、94C9C0 及三個計數字串另有[固定 replay](roster_departure_callee_replay.py)與[evidence](roster_departure_callee_evidence.json)／[recheck](roster_departure_callee_evidence_recheck.json)。兩份 JSON 相同，SHA-256 為 `04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0`；94C9C0 程式碼在 94D299 結束，後續 padding 與三張 RVA 表分列，未當指令。下一個有限切點是 94BE10 中已傳入 count 的完整局部用途，取得足以決定八人計算／資料／資源改動或具體外部缺口的證據便停止。

在決定八格 emitter 的通知語義前，需取得（或明示採用的新候選契約）pending 進入此 pre-removal stage 的條件、回呼期間 state 穩定／重入規則，以及 `94C9C0→94BE10` 玩家數使用的必要範圍。不能以 n<D 的新拒絕默默縮小完整目標，也不能把 raw source clone 可解碼、離線 synthetic 成功等同八個真實帳號可加入並退出同一場任務。

本輪完成的是六個直接讀取、額外 getter 依賴、同 context 前後派發、原副作用順序及 count 下游限制的有限前提清單。沒有 live 驗證、沒有完整外部 callback 閉合、沒有 executable 安裝成品。
