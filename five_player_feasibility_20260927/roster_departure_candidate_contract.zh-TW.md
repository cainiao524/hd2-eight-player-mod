# 605950／606820 與共同 B：departure 候選的有限完整契約

## 1. 可實作範圍與明確界限

可以依目前固定來源實作一個受明示契約限制的完整 `605950` 候選：保留完整控制流及資源 callback，六個直接 roster 讀取接到共同八格 B，處理 `6059EE→606820` 額外 reader，並將兩個「移除後 dense count」參數定義為 `D0−(n0<D0)`。這個公式是新增候選語義；已保存 caller 沒有直接否決它，但也没有證明 pending 可達或真實通知契約。

成品需求是原 entity 經八格儲存、原清理次序與後续 removal 仍對應同一 ID／ordinal。局部候選不能依 n<D 排除 pending 代替完整處理，也不能把 callback stub 不修改 roster 當成引擎同步證明。

本輪只核既有完整 root／callee evidence、`FDC820` 及必要已定位 `FD9D40`。沒有泛掃 caller/callee、新 capture、程序操作、候選 source／test／manifest 修改。

## 2. 固定來源

| 來源 | SHA-256 |
| --- | --- |
| `roster_departure_native_evidence.json` | `0280267b6f32d4a24f15c69da317d1c2c7a93adb136d4252ff93e09a8d67e609` |
| `roster_departure_callee_evidence.json` | `04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0` |
| `roster_property_apply_evidence_v3.json` | `d0dd9c02db933c20801a366d9668131734a29106e46f8a8a0d0de43981a27d22` |
| `605950..605F2F`：1503B／346 instructions／13 fragments | `4f0de56eb062df3180f58fcf4fd9a4e462eceba75a3077ac2bc22728500f5681` |
| `606820..6068E5`：197B／51 instructions／3 fragments | `0ee6495101f1fbd8c4a95731144aa5dbd43289f107264c12c4d2d9aab9ffd2ce` |
| `FDC820..FDCDFF`：1503B | `8ef7ad9fbf59756023045f94c796bfb96a2f43876d8c64052c0d306a8b5c6094` |

原 capture 的 report/data SHA 分別為 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`、`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。上表的原始指令、片段、62 個局部分支、45 個外部 relocation 及兩個間接控制點可直接從固定 JSON 重核，無須掃描其他 code。

## 3. 入口狀態與真正的第一次回呼

定義：S 為 global `3326468` 所指 roster；B 為該 S 綁定的 `680h` 八格 storage；T=`S+80h`、D=`S+84h`、P=`S+88h`；target 來自 RDX，ID=`target+8`；n 為同 S map 查得的 ordinal。

### 必須在第一次副作用前成立的狀態

- global S 與指定 binding S 相同；B 的四陣列、S/map 與 target 都是有效、持續存活的物件。
- `0<=P<=D<=T<=8`，且該次請求確有 member `n<T`。
- ID 不等 invalid-ID sentinel 或 map empty key；map 查找確實命中該 ID，沒有用空 bucket 的舊 value 當 ordinal。
- 若沿用共同候選的固定八-bucket 查找，map capacity 必須為8。這是候選的固定 map 契約；不是宣稱原函式只支援8。
- `B[n].pointer` 非 null，對應同一 target ID；唯一 ID、pointer 所有權及全 map bijection 不由一次 lookup 全面證明。
- 與後续 remove 整合時，dense prefix 的 flags／P 分段須滿足既有 remove 的有效狀態契約；不要將 pending 全部判為非法。

原 lookup 成功在 `605B84` 載入 EDI=n，`605B89` 設 EBX=FFFFFFFF；`605B96` 首次讀 pointer[n]。在 flag／mode 成立時，**`605BC9 call 13462C0` 的 disconnected 是第一個可能的外部回呼**，早於表面位址較低的 `6059EE`。初始 map lookup 本身沒有 external call。

目前實作已選以下第一種原入口之前的guard；第二種僅保留為曾評估的設計，並非目前source行為：

1. **原 prologue 之前的乾式入口檢查。** 保存／還原輸入參數及所使用的 nonvolatile，成功才進完整 clone。其暫存 stack writes 應明示；失敗必須還原 entry RSP／nonvolatile，再轉至明確 reject continuation。不能宣稱完全無記憶體寫入。
2. **保留原 lookup 的分段檢查。** 原 prologue 全部 saves 在 `605975` 完成後，於 `605978` 之前核 target／binding／counts。把原 `6059D4` miss、`605B90` invalid ordinal 導向拒絕，並在 `605B96` 前核 ordinal／pointer ID、保存快照。若 guard 改動 RDX，須在回到 `605978 mov EAX,[RDX+8]` 前還原 target。

第二方案不必額外重做一次查找，但需要確保所有 miss／invalid 分支都受到處理。若第一方案保留原 lookup，兩次查找之間雖沒有 callback，仍須由同步契約排除其他執行緒改寫。

**`6059DB` 或 `605A5B` 才做首次 guard 都太晚。** 前者之前可能已發 disconnected，後者之前還可能讀 network index、發关联通知及做三個 primary registration 清理。拒絕的外層行為仍需整合；原 `FDC820` 可能繼續其他派發，局部 reject 不能自行回復先前 caller 工作。

## 4. 六處直接讀取與额外 reader

| 原位點 | 原資料 | 八格位置 |
| --- | --- | --- |
| `605A0D` | `[R13+RCX*8+E8h]`，RCX=n | `B+n*8` |
| `605B96` | `[R13+RDI*8+E8h]`，RDI=n | `B+n*8` |
| `605A26` | `[RDI+R13+108h]`，RDI=n*70h | `B+40h+n*70h` 的首 DWORD |
| `605A3A` | 同上，第二 helper 前重讀 | 同上 |
| `605A4E` | 同上，第三 helper 前重讀 | 同上 |
| `605A5B` | `[RSI+R13+3A8h]`，RSI=n*20h | `B+580h+n*20h` 的首 DWORD |

原 R13 必須繼續是 S，不得永久改成 B 或 B bias。若使用 scratch register 改 operand，每個位點都要核原 live-state；不能僅因它是 volatile 就假設當下無值。原三次 primary DWORD 重讀的順序必須保留，不能合併成單一 cached value。

`6059EE` 呼叫的 `606820` 另有 `60683A/6068CE` 兩處 property+Ch network index 讀取，六處本地改接本身不足。可採以下之一並明列契約：

- 完整 clone explicit-S `606820`，兩處 network 讀取接 B；或
- 僅把 `6059EE` callsite 改向既有八格 getter。該位點返回後只消費 EAX，隨即重新載入 RCX，足以保持正常有效 lookup 的呼叫端資料流；但既有 getter 取 global S，故需 `global S == held R13 == binding S`，且 map／B／ID 在 callback 期間維持同一身分。新 getter 的拒絕／missing 不與原 explicit reader 的非法讀取等價。

不得因此全域替换 `606820`。在候選合法狀態域內，入口 member 驗證與狀態穩定契約應使此 call 的成功查找成立；原 miss 處理不作正常相容性案例。

### 三個 primary helper 是否暗中讀舊 inline arrays

完整 `B0B020`、`B11C20`、`B0F820` 各420B/104 instructions 已核：RDX=S 保存到 R12，只用於與外部24-byte registration tuple owner pointer 比較；R8D target ID 保存至 R15D，與 tuple+10h 比較。沒有以 S 讀 pointer／primary／aux／property inline arrays，也沒有把 S 改作新的 array base。

因此這三個 helper 的原 S 身分應保留，**不需要再為它們的 S-relative roster 陣列改接追加位置**。它們會移除 tuple、以尾 tuple 補洞／扣 count，或在特定 mode 清 pointer；list 變空時可釋放 backing、清 descriptor、更新子系統 count 並呼叫 map cleanup。六處加額外 reader 足以處理這組已證的直接 roster 讀取；資源 ownership、間接釋放與全程 callback 效果仍不能由此宣稱完成。

## 5. 新 count 政策與原 caller 的證據強度

在第一個 callback 前，以入口 n0、D0 計算並保存 remainingD，同時保存 n0；目前source沒有另外保存D0。政策定義：

```text
remainingD = D0 - (n0 < D0 ? 1 : 0)
```

在 `n0<T<=8`、`D0<=T` 下：dense target 必有 D0>=1，故不下溢；pending target 保留 D0，包括 D0=0。remainingD 的範圍為0..7。它與已實作 remove 候選的 D 變化一致。

| 合成有效分段 | 新兩個參數 | 原兩個參數 | 尾部 D（狀態穩定時） |
| --- | ---: | ---: | ---: |
| T=1,D=1,n=0 | 0 | 0 | 1 |
| T=8,D=5,n=2 | 4 | 4 | 5 |
| T=8,D=5,n=6 | 5 | 4 | 5 |
| T=1,D=0,n=0 | 0 | FFFFFFFF | 0 |

將 `605E95/605EF1` 原讀 D 改為讀 remainingD，移除 `605EA2/605EF8` 的 DEC，即可分別保留傳给 `94C9C0` 與 `60C2A0` 的位置及其餘 ABI。這兩個 DEC 後的 flags 都會在真正消費前被原指令或 callee 重定義；實作仍應做完整資料流／指令對照。

尾部 `605F0D` 的原指令是**當時重新讀取 `[R13+84h]`**，不是無條件返回 entry snapshot。可以保留此原指令；只有在 D 不被 callbacks 改動的契約下，這才等於 old D0。若改為 snapshot D0，必須同樣明列穩定性前提，不能稱在有重入時仍與原語義相同。

已保存 `FDC820` 的同 context 派發證明：`540B20→605950` 清理在 `540A40` 實際移除前；但不含同 S 的 n<D 限制。未找到直接否決上述新政策的固定指令，也未找到證明所有 pending 真實可達、或兩個消費者必須采用這個未來 D 的契約。政策只能作明示的新候選規則；原 tail D 與兩個 remainingD 分別保留，不能混成同一通知值。

v0.11 的 player_count 局部補丁可在獨立整合時消費0..7，其中 raw0仍按原規則變1；它沒有替 departure 決定這個公式。`60C2A0` 對0及5..7仍走原 numeric fallback，沒有新增資源 hash。

## 6. Frame 保存方案

原 entry RSP=E，push三個nonvolatile再sub80h，body X=E−98h。目前實作將sub/add同時改90h，新 body X'=E−A8h；實際只使用以下兩個DWORD，不把原四local設計提案當成已實作：

| 新 local | 實際內容 |
| --- | --- |
| `+60h` | remainingD |
| `+64h` | n0 |

目前entry guard完成查找與驗證後，以R10D攜帶remainingD、R11D攜帶n0，還原參數／使用的nonvolatile再進原prologue；原prologue沒有覆寫R10/R11。在原`605978`之前插入兩條stores到新frame+60/+64，早於原`605B96`指標讀取及`605BC9`callback。後來原lookup會重新給EDI ordinal；更後面RDI變成n*70h及其他manager，不能一路把它當ordinal。`+68/+6Ch`未作D0／ID0快照；tail仍為原current-D讀取。

保持原物理 save／local 位址的方法：所有原 RSP-relative operands `>=60h` 加10h；`20h..50h` outgoing argument offsets 保持原數值；四個依 RAX=entry RSP 的原保存地址保持。完整已知重定位集合：

| 原位點 | 原 RSP offset | 新 offset |
| --- | ---: | ---: |
| `605A63 / 605F18` XMM6 save/restore | 60h | 70h |
| `605AD8 / 605D0E` R15 save/restore | 70h | 80h |
| `605E33` R14 restore | 78h | 88h |
| `605D3E / 605D82 / 605D9F` 出參 DWORD 地址／讀回 | A0h | B0h |
| `605E38` RBP restore | A8h | B8h |
| `605DD4` RSI restore | B0h | C0h |
| `605BF9 / 605C48` R12 save/restore | B8h | C8h |

**70h→80h、78h→88h 跨過正 disp8 上界，必須重新編碼成 disp32，不能只替換一個 byte。** 新 XMM6 slot 仍16-byte對齊；sub增加16保持所有 call 的原16-byte對齊。`605D3E LEA RDX` 指向 out DWORD 的 address escape 也必須同改，不能只改後續讀取。

原 RAX-entry saves 為 `[E+8]=RCX`、`[E+10h]=RBP`、`[E+18h]=RSI`、`[E−20h]=R14`；尤其 `605950` 至 `605971` 之間 RAX 仍承擔 entry pointer，不能任意當 guard scratch。新 locals 不得挪用 outgoing `+20..50` 或原 XMM6 區域。

## 7. 同步／重新查詢不能互相替代

快照只保存了選定數值，沒有凍結其對應實體。完整候選須假定：從入口 guard 至最後通知之間，同 S binding、target ID／pointer、map ordinal、B storage 及 P/D/T 不被其他執行緒或 callback 改動，並遵守原 helper 對各子系統的資源契約。

三個 primary helper 可能修改其外部 registration；其他 manager callback 可操作 queue 或發事件。這些原資源操作仍應執行；不應為方便保持 count 而 stub／刪除它們。

每次 callback 後重新 lookup 可以發現某些變動，但不能回復之前已發出的通知或已釋放的 registration。entry binding 相等、或中途重新取得當時的 ordinal，都不能自行證明整段同步。若要在真實環境支援重入／失敗，需另外有可接合的同步或恢復契約；目前局部候選應明列不支援此未證範圍。

## 8. 必要長支線的 ABI 保留

原 `605D34 call FD9D40` 之後立即把 ECX 複製至 R8D，並讀 `[RAX+Ch]` 作 R9D。`FD9D40..FD9DF2` 完整178B／45 instructions，SHA：

```text
27627b0418666a4ce50917587d9dd779c3736a8af2272a3a3c955f94cb3701ed
```

該完整 body 沒有 ECX 目的寫入，也沒有 CALL，所以確實保留輸入的關聯 ID。成功返回為 global context `346BF98` 的 `+F32F18+ordinal*18h` record。其 map 位於 `+F1AEB0` pointer、`+F1AEB8` capacity、`+F1AEBC` empty、`+F1AEC0` multiplier。cap0／full-scan miss 有機會解參零指標，測試不得把任意 miss 都替換成安全 null。

固定原 bytes 可由同 capture `Image.read(0xFD9D40,0xB2)` 重核：

```text
4883ec083b0d029f4a020f849b0000004c8b15412249024533c048895c2410488974241848893c24458b8ab8aef100458b9ac0aef100440fafd9418d71ff4585c9743d498b9ab0aef100418bbabcaef1000f1f40006666660f1f8400000000008bc6438d14184823d0488d04d38b14d33bd7740e3bd1740a41ffc0453bc172e033c0488b3c24488b742418488b5c2410390875178b4004488d0440488d80e3651e00498d04c24883c408c333c04883c408c3
```

`13BFB40` 在此位點的 ABI 為 RCX=`[346D500]`、RDX=&outDWORD、R8D=保留的關聯ID、R9D=`[resolved+Ch]`；stack `+20=1`、`+28=float0`、`+30 byte1`、`+38 DWORD0`、`+40 DWORD0`、`+48 float0`、`+50 byte0`。其他 caller ABI 及先後已列在原 departure prerequisites；特別是 `838680` 的 RCX 來自之前間接 callback，原 caller 沒有在 call 前重新給定，不能擅自假設其等於 S。

測試可把未展開 callback 的預期參數、out DWORD、呼叫先後及對 roster 不干擾列為明示契約。若以任意 volatile clobber 替身模擬 FD9D40，會破壞原實际 ECX 資料流；應執行該固定 body 或精確描述它的保留行為。

## 9. 完整函式 relocation 的必要處理

- 完整來源為346 instructions／13 fragments，包含命中後位於較後 RVA 的 callback 段、回跳主段與條件保存的 nonvolatile。不能只搬最前連續區段或以第一個高位 RET 猜 extent；原 root 本身以間接 JMP 結束。
- 62 個 local branches 要全部映射到新位置；插入 guard、移除 DEC、增大 memory displacement 或升級 short Jcc/JMP 都會改變 layout。拒絕任何進入新指令 interior 的 target。
- 45 個外部 relocations 包含21個 direct calls、22個 RIP memory、2個 RIP LEA 字串地址。逐一保留或明列唯一額外 reader callsite 替換；不能因 source在同image便原樣複製rel32。
- 保留 `605AC8 call RAX` 與 `605F28 JMP [R8+480h]` 的原間接派發；尾跳前 frame／NV／XMM6 及參數必須完整恢復。
- 原有 R15／R12 只在某些分支保存與恢復，不能讓新增分支走到未保存的 restore。reject 若在部分 prologue 之後，必须只恢復該路徑已保存的值；原入口之前 guard 的 reject 可避免與這些條件 save 交錯。
- array 改寫需要處理 R13 為 SIB index 的 operand，不能只改常见 base-register 位元；每次改接後仍保留 R13=S供 helper owner 身分使用。
- 新frame、clone、reject與trampoline皆須考慮原非leaf Windows unwind、code-range交疊、rel32可達性、共同B身分及已存在candidate區域。離線byte建置不提供執行中原子替換、unwind註冊或回復。

## 10. 候選驗證及停止條件

有限但有意義的測試應覆蓋：首次 callback 前的合法／拒絕路徑；八個 ordinal 的六處讀取與getter；所有合法dense/pending分段的兩個remainingD參數與原tailD；原四格dense配對；pending D=0不下溢；primary三個calls的原S/ID/value及資源次序；短路與關聯entity長分支；完整frame、out參、nonvolatile和尾跳。

原資源callee與必要callback替身要分開列：實際執行的固定helper可以證明其指令行為，受控事件／allocator契約不能替代真实資源、回呼重入或失敗恢復。出現已發生副作用後的新reject時，不能宣称failure atomic。

目前已足以產生受上述契約限制的完整離線候選及有界指令對照。真正剩餘的阻礙是entry條件的真實caller來源、state穩定／重入、資源有效性與通知的業務契約，以及執行整合／八帳號驗收。這些保留為明確限制，不需要繼續泛搜無關callee才能開始本地候選。
